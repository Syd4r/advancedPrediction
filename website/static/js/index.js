document.addEventListener("keypress", (e) => {
    if (e.key == "`") {
        e.preventDefault();
        openSidebar();
    }
});

const timerDuration = 10 * 60;
let remainingSeconds = timerDuration;
let timerRunning = false;
let timerInterval = null;

const timerDisplay = document.getElementById("timer-display");
const timerToggle = document.getElementById("timer-toggle");
const timerReset = document.getElementById("timer-reset");

function renderTimer() {
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    timerDisplay.textContent =
        `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function stopTimer() {
    timerRunning = false;
    if (timerInterval !== null) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    timerToggle.textContent = "Play";
}

timerToggle.addEventListener("click", () => {
    if (remainingSeconds === 0) {
        remainingSeconds = timerDuration;
        renderTimer();
    }

    if (timerRunning) {
        stopTimer();
        return;
    }

    timerRunning = true;
    timerToggle.textContent = "Pause";
    timerInterval = setInterval(() => {
        remainingSeconds -= 1;
        if (remainingSeconds <= 0) {
            remainingSeconds = 0;
            renderTimer();
            stopTimer();
            return;
        }
        renderTimer();
    }, 1000);
});

timerReset.addEventListener("click", () => {
    stopTimer();
    remainingSeconds = timerDuration;
    renderTimer();
});

renderTimer();

sidebarOpen = false;
let generationEnabled = true;
let generationRequestId = 0;

function openSidebar() {
    leftPadding = document.getElementById("left-padding");
    rightSidebar = document.getElementById("right-sidebar");
    if (sidebarOpen) {
        rightSidebar.classList.add("hidden");
        leftPadding.classList.remove("hidden");
    } else {
        rightSidebar.classList.remove("hidden");
        leftPadding.classList.add("hidden");
        triggerGeneration();
    }
    sidebarOpen = !sidebarOpen;
}

async function triggerGeneration() {
    if (!generationEnabled) {
        return;
    }

    allText = document.getElementById("main-doc").value;
    words = allText.split(" ");
    
    suggestions = document.getElementById("suggestions");
    suggestionsNone = document.getElementById("suggestions-none");
    loading = document.getElementById("suggestions-loading");
    if (words.length > 10) {
        suggestionsNone.classList.add("hidden");
        suggestions.classList.add("hidden");
        loading.classList.remove("hidden");
    } else {
        suggestions.classList.add("hidden");
        loading.classList.add("hidden");
        suggestionsNone.classList.remove("hidden");
        suggestionsNone.textContent =
            "Suggestions will appear once more text is written.";
        return;
    }

    userPrompt = document.getElementById("user-prompt").value;

    profSlider = document.getElementById("range-prof").value;
    exprSlider = document.getElementById("range-expr").value;
    verbSlider = document.getElementById("range-verb").value;

    const editor = document.getElementById("main-doc");

    const text = editor.value;
    const cursor = editor.selectionStart;
    const paragraphStart = text.lastIndexOf("\n", cursor - 1) + 1;

    let paragraphEnd = text.indexOf("\n", cursor);
    if (paragraphEnd === -1) {
        paragraphEnd = text.length;
    }

    const textBeforeCursor = text.substring(0, cursor);
    const textAfterCursor = text.substring(cursor);
    const currentParagraph = text.substring(
        paragraphStart,
        cursor
    ).trimEnd();

    const beforeCharacter = text[cursor - 1] || "";
    const afterCharacter = text[cursor] || "";
    const cursorSentenceComplete = /[.!?][\s"'')\]]*$/.test(
        textBeforeCursor
    );

    let cursorState = "MID_SENTENCE";
    if (/^\s*$/.test(textBeforeCursor) && /^\s*$/.test(textAfterCursor)) {
        cursorState = "EMPTY_OR_WHITESPACE";
    } else if (
        /\w/.test(beforeCharacter)
        && /\w/.test(afterCharacter)
    ) {
        cursorState = "MID_WORD";
    } else if (cursorSentenceComplete) {
        cursorState = "SENTENCE_END";
    } else if (
        cursor === text.length
        && /\n\s*\n/.test(textBeforeCursor.slice(-2))
    ) {
        cursorState = "PARAGRAPH_END";
    }

    const previousText = text.substring(0, paragraphStart).trimEnd();
    const previousParagraphs = previousText
        .split(/\n\s*\n/)
        .slice(-2)
        .join("\n\n");

    const submit_data = {
        intention: userPrompt,
        previous_paragraphs: previousParagraphs,
        current_paragraph: currentParagraph,
        text_before_cursor: textBeforeCursor,
        text_after_cursor: textAfterCursor,
        cursor_position: cursor,
        cursor_state: cursorState,
        professionalism: profSlider,
        expression: exprSlider,
        verbosity: verbSlider
    };
    const requestId = ++generationRequestId;
    try {

        // Send request to Flask
        const response = await fetch("/generate-suggestions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(submit_data)
        });

        const data = await response.json();

        if (requestId !== generationRequestId || !generationEnabled) {
            return;
        }

        if (!response.ok || !data.success) {
            throw new Error(data.error || "Generation failed.");
        }

        for (let i = 0; i < 12; i++) {
            document.getElementById(`suggestion-${i}`).textContent = "";
        }

        // Populate suggestion elements
        const suggestionsList = Array.isArray(data.suggestions)
            ? data.suggestions.slice(0, 12)
            : [];

        suggestionsList.forEach((suggestion, i) => {

            const suggestionElement =
                document.getElementById(`suggestion-${i}`);

            suggestionElement.textContent = suggestion;

        });

        loading.classList.add("hidden");
        if (suggestionsList.length === 0) {
            suggestions.classList.add("hidden");
            suggestionsNone.classList.remove("hidden");
            suggestionsNone.textContent =
                "No suggestions were generated. Reload to try again.";
        } else {
            suggestions.classList.remove("hidden");
            suggestionsNone.classList.add("hidden");
        }

    } catch (error) {

        if (requestId !== generationRequestId || !generationEnabled) {
            return;
        }

        console.error("Suggestion generation error:", error);

        for (let i = 0; i < 12; i++) {
            document.getElementById(`suggestion-${i}`).textContent =
                "Generation failed";
        }

        loading.classList.add("hidden");
        suggestions.classList.remove("hidden");

    } finally {
        if (requestId === generationRequestId) {
            loading.classList.add("hidden");
        }
    }
}

const generationToggle = document.getElementById("generation-toggle");
const reloadSuggestions = document.getElementById("reload-suggestions");

generationToggle.addEventListener("change", () => {
    generationEnabled = generationToggle.checked;
    reloadSuggestions.disabled = !generationEnabled;

    if (!generationEnabled) {
        generationRequestId++;
        document.getElementById("suggestions-loading").classList.add("hidden");
        document.getElementById("suggestions").classList.add("hidden");
        suggestionsNone = document.getElementById("suggestions-none");
        suggestionsNone.textContent = "Suggestions are turned off.";
        suggestionsNone.classList.remove("hidden");
    } else {
        suggestionsNone = document.getElementById("suggestions-none");
        triggerGeneration();
    }
});

reloadSuggestions.addEventListener("click", () => {
    triggerGeneration();
});


const mainDoc = document.getElementById("main-doc");

for (let i = 0; i < 12; i++) {

    const suggestion = document.getElementById(`suggestion-${i}`);

    suggestion.addEventListener("click", () => {

        const text = suggestion.textContent;

        if (!text || text === "Loading..." || text === "Generation failed") {
            return;
        }

        const start = mainDoc.selectionStart;
        const end = mainDoc.selectionEnd;

        mainDoc.setRangeText(
            text+" ",
            start,
            end,
            "end"
        );

        mainDoc.focus();
        triggerGeneration();
    });

}
