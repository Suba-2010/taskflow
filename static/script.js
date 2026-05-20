document.addEventListener("DOMContentLoaded", function () {
    const bars = document.querySelectorAll(".progress-bar");

    bars.forEach(bar => {
        const width = bar.getAttribute("data-width");
        bar.style.width = width + "%";
    });
});
// Dark Mode Toggle
document.addEventListener("DOMContentLoaded", function () {
    const toggle = document.getElementById("theme-toggle");

    // Load saved theme
    if (localStorage.getItem("theme") === "dark") {
        document.body.classList.add("dark-mode");
        if (toggle) {
            toggle.textContent = "☀️ Light Mode";
        }
    }

    // Toggle theme
    if (toggle) {
        toggle.addEventListener("click", function () {
            document.body.classList.toggle("dark-mode");

            if (document.body.classList.contains("dark-mode")) {
                localStorage.setItem("theme", "dark");
                toggle.textContent = "☀️ Light Mode";
            } else {
                localStorage.setItem("theme", "light");
                toggle.textContent = "🌙 Dark Mode";
            }
        });
    }

    // Progress bar width (if used)
    const bars = document.querySelectorAll(".progress-bar");
    bars.forEach(bar => {
        const width = bar.getAttribute("data-width");
        if (width) {
            bar.style.width = width + "%";
        }
    });
});