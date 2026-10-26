document.addEventListener("DOMContentLoaded", () => {
    const canvas = document.getElementById("profitChart");
    const dataElement = document.getElementById("chart-data");

    if (!canvas || !dataElement) return;

    let profits;

    try {
        profits = JSON.parse(dataElement.textContent);
    } catch (error) {
        console.error("Unable to load chart data.");
        return;
    }

    const ctx = canvas.getContext("2d");

    if (!ctx) return;

    // Build cumulative profit/loss, starting at $0.
    const cumulative = [0];
    let runningTotal = 0;

    profits.forEach(profit => {
        runningTotal += profit / 100;
        cumulative.push(runningTotal);
    });

    function drawChart() {
        const rect = canvas.getBoundingClientRect();

        if (!rect.width || !rect.height) return;

        const dpr = window.devicePixelRatio || 1;

        canvas.width = Math.round(rect.width * dpr);
        canvas.height = Math.round(rect.height * dpr);

        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

        const width = rect.width;
        const height = rect.height;

        ctx.clearRect(0, 0, width, height);

        const left = 55;
        const right = 15;
        const top = 20;
        const bottom = 35;

        const chartWidth = width - left - right;
        const chartHeight = height - top - bottom;

        const minValue = Math.min(0, ...cumulative);
        const maxValue = Math.max(0, ...cumulative);

        const padding = Math.max((maxValue - minValue) * 0.15, 5);

        const minY = minValue - padding;
        const maxY = maxValue + padding;

        function xPosition(index) {
            return left + (index / Math.max(cumulative.length - 1, 1)) * chartWidth;
        }

        function yPosition(value) {
            return top + ((maxY - value) / (maxY - minY)) * chartHeight;
        }

        // Horizontal grid lines and dollar labels.
        ctx.font = "11px sans-serif";
        ctx.textAlign = "right";

        for (let i = 0; i <= 4; i++) {
            const value = maxY - (i / 4) * (maxY - minY);
            const y = yPosition(value);

            ctx.strokeStyle = "rgba(216,182,106,0.12)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(left, y);
            ctx.lineTo(width - right, y);
            ctx.stroke();

            ctx.fillStyle = "#9aaa9e";
            ctx.fillText(
                (value < 0 ? "-$" : "$") + Math.abs(value).toFixed(0),
                left - 8,
                y + 4
            );
        }

        // Zero-profit reference line.
        ctx.setLineDash([5, 5]);
        ctx.strokeStyle = "rgba(255,255,255,0.3)";
        ctx.beginPath();
        ctx.moveTo(left, yPosition(0));
        ctx.lineTo(width - right, yPosition(0));
        ctx.stroke();
        ctx.setLineDash([]);

        const isPositive = runningTotal >= 0;
        const lineColor = isPositive ? "#68d7a0" : "#e47777";

        // Gradient below the line.
        const gradient = ctx.createLinearGradient(0, top, 0, height);
        gradient.addColorStop(
            0,
            isPositive ? "rgba(104,215,160,0.25)" : "rgba(228,119,119,0.25)"
        );
        gradient.addColorStop(1, "rgba(0,0,0,0)");

        ctx.beginPath();

        cumulative.forEach((value, index) => {
            const x = xPosition(index);
            const y = yPosition(value);

            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });

        ctx.lineTo(xPosition(cumulative.length - 1), yPosition(minY));
        ctx.lineTo(xPosition(0), yPosition(minY));
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // Profit/loss line.
        ctx.beginPath();

        cumulative.forEach((value, index) => {
            const x = xPosition(index);
            const y = yPosition(value);

            if (index === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });

        ctx.strokeStyle = lineColor;
        ctx.lineWidth = 3;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        ctx.stroke();

        // Current result marker.
        const lastIndex = cumulative.length - 1;

        ctx.beginPath();
        ctx.arc(
            xPosition(lastIndex),
            yPosition(cumulative[lastIndex]),
            5,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "#d8b66a";
        ctx.fill();

        // X-axis labels.
        ctx.fillStyle = "#9aaa9e";
        ctx.textAlign = "left";
        ctx.fillText("Start", left, height - 10);

        ctx.textAlign = "right";
        ctx.fillText(
            `${profits.length} sessions`,
            width - right,
            height - 10
        );
    }

    drawChart();

    window.addEventListener("resize", drawChart);
});

// Session entry form behavior
document.addEventListener("DOMContentLoaded", () => {
    const mode = document.getElementById("entry-mode");
    const buyinFields = document.getElementById("buyin-fields");
    const netFields = document.getElementById("net-fields");
    const dateField = document.getElementById("session-date");

    if (dateField) {
        const today = new Date();
        const localDate = new Date(
            today.getTime() - today.getTimezoneOffset() * 60000
        ).toISOString().slice(0, 10);

        dateField.value = localDate;
        dateField.max = localDate;
    }

    if (!mode || !buyinFields || !netFields) return;

    function updateMode() {
        const netOnly = mode.value === "net";

        buyinFields.hidden = netOnly;
        netFields.hidden = !netOnly;

        buyinFields.querySelectorAll("input").forEach(input => {
            input.required = !netOnly;
            input.disabled = netOnly;
        });

        netFields.querySelectorAll("input").forEach(input => {
            input.required = netOnly;
            input.disabled = !netOnly;
        });
    }

    mode.addEventListener("change", updateMode);
    updateMode();
});

/* Individual session history pagination */
document.addEventListener("DOMContentLoaded", () => {
    const table = document.getElementById("session-history-table");
    const pagination = document.getElementById("session-pagination");
    const info = document.getElementById("session-page-info");
    const buttons = document.getElementById("session-page-buttons");

    if (!table || !pagination || !info || !buttons) return;

    const rows = Array.from(table.querySelectorAll("tbody tr"))
        .filter(row => !row.querySelector(".empty-state"));

    const perPage = 10;
    const totalPages = Math.ceil(rows.length / perPage);
    let currentPage = 1;

    if (totalPages <= 1) return;

    pagination.hidden = false;

    function renderPage() {
        const start = (currentPage - 1) * perPage;
        const end = Math.min(start + perPage, rows.length);

        rows.forEach((row, index) => {
            row.hidden = index < start || index >= end;
            row.style.display = row.hidden ? "none" : "";
        });

        info.textContent =
            `Showing ${start + 1}–${end} of ${rows.length} sessions`;

        buttons.replaceChildren();

        function addButton(label, page, disabled, active = false) {
            const button = document.createElement("button");
            button.type = "button";
            button.textContent = label;
            button.disabled = disabled;
            button.className = active ? "page-button active" : "page-button";

            button.addEventListener("click", () => {
                currentPage = page;
                renderPage();
                document.getElementById("session-history")
                    ?.scrollIntoView({ behavior: "smooth" });
            });

            buttons.appendChild(button);
        }

        addButton("‹", currentPage - 1, currentPage === 1);

        for (let page = 1; page <= totalPages; page++) {
            if (
                page === 1 ||
                page === totalPages ||
                Math.abs(page - currentPage) <= 1
            ) {
                addButton(String(page), page, false, page === currentPage);
            } else if (
                page === 2 && currentPage > 3 ||
                page === totalPages - 1 && currentPage < totalPages - 2
            ) {
                const dots = document.createElement("span");
                dots.textContent = "…";
                buttons.appendChild(dots);
            }
        }

        addButton("›", currentPage + 1, currentPage === totalPages);
    }

    renderPage();
});

// Mobile analytics expand/collapse
document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector(".mobile-analytics-details");
    const analytics = document.querySelector("#mobile-analytics-content");

    if (!toggle || !analytics) return;

    toggle.addEventListener("toggle", () => {
        analytics.style.display = toggle.open ? "" : "none";
    });
});

// Expand/collapse leaderboard on mobile
document.addEventListener("DOMContentLoaded", () => {
    const board = document.querySelector("#leaderboard");
    const button = document.querySelector(".mobile-leaderboard-toggle");

    if (!board || !button) return;

    button.addEventListener("click", () => {
        const expanded = board.classList.toggle("leaderboard-expanded");
        button.textContent = expanded ? "Show Top 3" : "Show All Rankings";
        button.setAttribute("aria-expanded", String(expanded));
    });
});

// Poker Ledger splash screen — minimum 1.5 seconds
(() => {
    const startedAt = performance.now();
    const minimumDuration = 1500;

    function hidePokerLoader() {
        const loader = document.getElementById("poker-loader");
        if (!loader) return;

        const elapsed = performance.now() - startedAt;
        const remaining = Math.max(0, minimumDuration - elapsed);

        setTimeout(() => {
            loader.classList.add("is-hidden");
            setTimeout(() => loader.remove(), 450);
        }, remaining);
    }

    if (document.readyState === "complete") {
        hidePokerLoader();
    } else {
        window.addEventListener("load", hidePokerLoader, { once: true });
    }
})();
