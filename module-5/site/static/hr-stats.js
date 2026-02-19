document.addEventListener("DOMContentLoaded", () => {
  const loadStatsButton = document.getElementById("load-stats-button");
  const statsTableBody = document.getElementById("stats-table-body");
  const processingIndicator = document.getElementById("processing-indicator");
  const errorMessage = document.getElementById("error-message");
  const resultsContainer = document.getElementById("results-container");
  const totalSummary = document.getElementById("total-summary");
  const statsTable = document.querySelector(".stats-table");

  loadStatsButton.addEventListener("click", async () => {
    // Reset UI
    processingIndicator.style.display = "block";
    errorMessage.style.display = "none";
    errorMessage.textContent = "";
    resultsContainer.style.display = "none";
    statsTableBody.innerHTML = "";
    totalSummary.textContent = "";

    try {
      // Use default query by not passing any query parameter
      const response = await fetch("/api/hr-stats", {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(
          errorData.detail || `HTTP error! status: ${response.status}`,
        );
      }

      const responseData = await response.json();
      console.log("HR Query results:", responseData);
      const data = responseData.function_response;

      // Check if we have data
      if (!data.data || data.data.length === 0) {
        errorMessage.textContent = "No data found from the query.";
        errorMessage.style.display = "block";
        return;
      }

      // Get the table element
      const statsTable = document.querySelector(".stats-table");
      const thead = statsTable.querySelector("thead tr");

      // Clear existing headers
      thead.innerHTML = "";

      // Dynamically create table headers based on columns
      data.columns.forEach((columnName) => {
        const th = document.createElement("th");
        // Format column name: replace underscores with spaces and capitalize
        th.textContent = columnName
          .split("_")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" ");
        thead.appendChild(th);
      });

      // Populate the table body with data
      data.data.forEach((row) => {
        const tr = document.createElement("tr");

        data.columns.forEach((columnName) => {
          const td = document.createElement("td");
          const value = row[columnName];
          td.textContent = value !== null && value !== undefined ? value : "";

          // Apply special styling if column is 'severity'
          if (columnName.toLowerCase() === "severity" && value) {
            const severityLower = value.toString().toLowerCase();
            if (severityLower.includes("high")) {
              td.classList.add("severity-high");
            } else if (severityLower.includes("medium")) {
              td.classList.add("severity-medium");
            } else if (severityLower.includes("low")) {
              td.classList.add("severity-low");
            }
          }

          tr.appendChild(td);
        });

        statsTableBody.appendChild(tr);
      });

      // Display summary
      totalSummary.textContent = `Total Records: ${data.total_records}`;

      // Calculate total if there's a numeric column that looks like a total
      const numericColumns = data.columns.filter(
        (col) =>
          col.toLowerCase().includes("total") ||
          col.toLowerCase().includes("count") ||
          col.toLowerCase().includes("violations"),
      );

      if (numericColumns.length > 0) {
        const totals = {};
        numericColumns.forEach((col) => {
          const sum = data.data.reduce((acc, row) => {
            const val = parseFloat(row[col]);
            return acc + (isNaN(val) ? 0 : val);
          }, 0);
          totals[col] = sum;
        });

        // Add totals to summary
        const totalStrings = Object.entries(totals).map(
          ([col, sum]) =>
            `${col
              .split("_")
              .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
              .join(" ")}: ${sum}`,
        );
        totalSummary.textContent = `Total Records: ${data.total_records} | ${totalStrings.join(" | ")}`;
      }

      // Show the results
      resultsContainer.style.display = "block";
    } catch (error) {
      console.error("Error fetching HR stats:", error);
      errorMessage.textContent = `An error occurred: ${error.message}`;
      errorMessage.style.display = "block";
    } finally {
      processingIndicator.style.display = "none";
    }
  });
});
