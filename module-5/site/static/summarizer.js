document.addEventListener("DOMContentLoaded", () => {
  const summarizeForm = document.getElementById("summarize-form");
  const urlInput = document.getElementById("url-input");
  const summaryOutput = document.getElementById("summary-output");
  const processingIndicator = document.getElementById("processing-indicator");

  summarizeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();

    if (!url) {
      summaryOutput.textContent = "Please enter a valid URL.";
      return;
    }

    processingIndicator.style.display = "block";
    summaryOutput.textContent = "";

    try {
      const response = await fetch("/api/summarize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url: url }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `HTTP error! status: ${response.status}`,
        );
      }

      const data = await response.json();
      summaryOutput.textContent = data.summary;
      console.log("Full summarize response", data);
    } catch (error) {
      console.error("Error fetching summary:", error);
      summaryOutput.textContent = `An error occurred: ${error.message}`;
    } finally {
      processingIndicator.style.display = "none";
    }
  });
});
