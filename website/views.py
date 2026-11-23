'''Views.py'''

import json
import re
import os
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from flask import Blueprint, jsonify, render_template, request
from openai import OpenAI


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=30
)

MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")

main_blueprint = Blueprint("main", __name__)


@main_blueprint.route("/")
def index():
    return render_template("index.html")


@main_blueprint.route("/generate-suggestions", methods=["POST"])
def generate_suggestions():
    try:
        data = request.get_json(silent=True) or {}

        intention = str(data.get("intention", "")).strip()
        previous_paragraphs = str(data.get("previous_paragraphs", "")).strip()
        current_paragraph = str(data.get("current_paragraph", "")).strip()
        text_before_cursor = str(
            data.get("text_before_cursor", current_paragraph)
        ).strip()
        text_after_cursor = str(data.get("text_after_cursor", "")).strip()
        cursor_position = int(data.get("cursor_position", 0))
        cursor_state = str(data.get("cursor_state", "")).strip()

        if cursor_state not in {
            "SENTENCE_END",
            "PARAGRAPH_END",
            "EMPTY_OR_WHITESPACE",
            "MID_WORD",
            "MID_SENTENCE",
        }:
            cursor_state = (
                "SENTENCE_END"
                if re.search(r"[.!?][\s\"')\]]*$", text_before_cursor)
                else "MID_SENTENCE"
            )

        professionalism = max(
            0, min(100, int(data.get("professionalism", 50)))
        )
        expression = max(
            0, min(100, int(data.get("expression", 50)))
        )
        verbosity = max(
            0, min(100, int(data.get("verbosity", 50)))
        )

        cursor_rules = {
            "SENTENCE_END": """
The cursor is after a completed sentence.
Generate a 1- or 2-word opening for a NEW sentence.
Use a subject, time/place phrase, narrative opening, or concrete
transition. Capitalize the opening. Do not use conjunctions or
continuation words such as and, but, because, though, while,
before, after, however, or therefore.
""",
            "PARAGRAPH_END": """
The cursor is at the end of a paragraph.
Generate a 1- or 2-word opening for the next sentence or paragraph.
It must be independent and capitalize naturally.
""",
            "EMPTY_OR_WHITESPACE": """
The cursor is in an empty or whitespace-only position.
Generate a 1- or 2-word beginning for a new thought or sentence.
The result must be useful on its own and capitalize naturally.
""",
            "MID_WORD": """
The cursor is inside a word.
Generate only a plausible word completion or inflection. The
completion must join directly to the text immediately before the
cursor and must not include a leading space or duplicate text.
""",
            "MID_SENTENCE": """
The cursor is inside or at the end of an unfinished sentence.
Generate words that naturally continue the existing sentence.
Do not start a complete new sentence.
""",
        }

        context = f"""
You are a concise writing assistant helping a user choose their next words.
You do not write for the user or produce complete sentences.

## WRITING CONTEXT

User intention:
{intention or "Not provided"}

Previous paragraphs:
{previous_paragraphs or "None"}

Full text before the cursor:
{text_before_cursor or "None"}

Current paragraph:
{current_paragraph or "None"}

Text after the cursor:
{text_after_cursor or "None"}

Cursor position: {cursor_position}
Cursor state: {cursor_state}

{cursor_rules[cursor_state]}

## STYLE

Professionalism: {professionalism}/100
0 is casual; 50 is balanced; 100 is formal.

Expressivity: {expression}/100
0 is neutral; 50 is balanced; 100 is vivid and descriptive.

Verbosity: {verbosity}/100
0 favors individual words; 50 allows individual or two-word phrases;
100 favors natural two-word phrases.

## STRICT REQUIREMENTS

- Return exactly 5 strings.
- Every string contains exactly 1 or 2 words.
- Do not repeat words or phrases already in the active sentence.
- Preserve the user's meaning, tense, point of view, and writing style.
- Do not generate explanations or Markdown.
- At sentence boundaries, never continue the previous sentence.
- At MID_SENTENCE, do not capitalize as though starting a new sentence.
- Vary sentence length: include some suggestions that could complete
  the active sentence and some that naturally extend it.
- At MID_SENTENCE, include roughly 2 suggestions ending with appropriate
  punctuation (such as periods, question marks, commas, or semicolons)
  and roughly 3 suggestions that continue the thought without forcing a
  sentence ending.
- Do not invent quotation marks or parenthetical punctuation.
- Punctuation-only suggestions are allowed only when the cursor is inside
  an unfinished sentence and the punctuation naturally fits that position.
- Return a valid JSON array of strings.

Examples:
["Meanwhile", "At sunrise", "Someone", "The morning"]
"""

        generation_types = [
            {
                "name": "Natural continuation",
                "instructions": """
Generate natural, conventional options.
When MID_SENTENCE, include a balanced mix of 2 plausible ways to
end the sentence and 3 ways to extend it.
Prioritize grammatical compatibility and the user's existing style.
""",
            },
            {
                "name": "Sentence completion",
                "instructions": """
Focus on satisfying endings.
When MID_SENTENCE, include several suggestions that naturally finish
the active sentence, including complete word/phrase endings with
punctuation and useful punctuation such as "." or "?".
At a sentence or paragraph boundary, generate a strong opening instead.
""",
            },
            {
                "name": "Extended expression",
                "instructions": """
Focus on extending the active thought in meaningful directions.
When MID_SENTENCE, include options that continue the clause or add
a related clause, while also offering a few shorter bridging phrases.
Avoid automatically ending every suggestion.
""",
            },
        ]

        def parse_suggestions(output_text):
            text = output_text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)

            parsed = json.loads(text)
            if not isinstance(parsed, list):
                raise ValueError("Model output is not a JSON array")
            return parsed

        def generate_category(category):
            prompt = f"""
{context}

## GENERATION OBJECTIVE

{category["instructions"]}

Before returning, verify every suggestion against the cursor state,
word count, grammar, punctuation, and duplicate rules.
"""

            response = client.responses.create(
                model=MODEL,
                reasoning={"effort": "none"},
                temperature=0.8,
                max_output_tokens=300,
                input=prompt
            )

            suggestions = parse_suggestions(response.output_text)
            prohibited_starters = {
                "and", "but", "or", "so", "because", "though",
                "although", "however", "therefore", "before",
                "after", "while", "yet", "since", "unless",
                "as", "if", "when"
            }

            valid_suggestions = []
            normalized_current_text = re.sub(
                r"[^\w\s]",
                "",
                text_before_cursor.lower()
            )
            normalized_current_text = re.sub(
                r"\s+", " ", normalized_current_text
            ).strip()

            for raw_suggestion in suggestions:
                if not isinstance(raw_suggestion, str):
                    continue

                suggestion = re.sub(r"\s+", " ", raw_suggestion).strip()
                if not 1 <= len(suggestion.split()) <= 2:
                    continue

                normalized_suggestion = re.sub(
                    r"[^\w\s]", "", suggestion.lower()
                )
                normalized_suggestion = re.sub(
                    r"\s+", " ", normalized_suggestion
                ).strip()
                if normalized_suggestion:
                    if re.search(
                        rf"(?:^|\s){re.escape(normalized_suggestion)}(?:$|\s)",
                        normalized_current_text
                    ):
                        continue

                if cursor_state in {
                    "SENTENCE_END",
                    "PARAGRAPH_END",
                    "EMPTY_OR_WHITESPACE",
                }:
                    first_match = re.search(r"[A-Za-z]+", suggestion)
                    first_word = (
                        first_match.group(0).lower()
                        if first_match
                        else ""
                    )

                    if (
                        first_word in prohibited_starters
                        or not suggestion[0].isalpha()
                    ):
                        continue

                    suggestion = suggestion[0].upper() + suggestion[1:]

                valid_suggestions.append(suggestion)

            return valid_suggestions

        def run_generation(categories):
            with ThreadPoolExecutor(max_workers=len(categories)) as executor:
                futures = [
                    executor.submit(generate_category, category)
                    for category in categories
                ]
                results = []
                for future in futures:
                    try:
                        results.append(
                            future.result(timeout=25)
                        )
                    except Exception as category_error:
                        print("Category generation error:", str(category_error))
                        results.append([])
            return results

        def collect_unique(category_results):
            unique = []
            seen = set()
            for category_suggestions in category_results:
                for suggestion in category_suggestions:
                    normalized = re.sub(r"\s+", " ", suggestion.lower()).strip()
                    if normalized and normalized not in seen:
                        seen.add(normalized)
                        unique.append(suggestion)
            return unique

        suggestions = collect_unique(run_generation(generation_types))

        if len(suggestions) < 4:
            retry_categories = generation_types
            retry_suggestions = collect_unique(
                run_generation(retry_categories)
            )
            suggestions = collect_unique([
                suggestions,
                retry_suggestions
            ])

        if len(suggestions) < 4:
            if cursor_state in {
                "SENTENCE_END",
                "PARAGRAPH_END",
                "EMPTY_OR_WHITESPACE",
            }:
                fallback = ["Meanwhile", "At that moment", "Suddenly", "Nevertheless"]
            elif cursor_state == "MID_WORD":
                fallback = ["s", "ed", "ing", "ly"]
            else:
                fallback = ["however", "then", "for now", "instead"]

            suggestions = collect_unique([
                suggestions,
                fallback
            ])

        return jsonify({
            "success": True,
            "suggestions": suggestions[:12]
        })

    except Exception as error:
        print("Generation error:", str(error))
        return jsonify({
            "success": False,
            "error": "Failed to generate suggestions."
        }), 500
