document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("clientSearch");
    const table = document.querySelector(".client-list table");

    if (!searchInput || !table) return;

    const tableRows = table.querySelectorAll("tbody tr");

    const noResults = document.createElement("p");
    noResults.className = "no-results";
    noResults.textContent = "No matching clients found.";
    noResults.style.display = "none";

    table.parentElement.appendChild(noResults);

    searchInput.addEventListener("input", function () {
        const searchValue = this.value.toLowerCase().trim();
        let visibleCount = 0;

        tableRows.forEach(row => {
            const rowText = row.textContent.toLowerCase();
            const matches = rowText.includes(searchValue);

            row.style.display = matches ? "" : "none";

            if (matches) visibleCount++;
        });

        noResults.style.display = visibleCount === 0 ? "block" : "none";
        table.style.display = visibleCount === 0 ? "none" : "table";
    });
});
