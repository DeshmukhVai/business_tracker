// Renders the three dashboard charts using Chart.js.
// Expects chartLabels, chartSales, chartExpenses, productLabels,
// productValues and statusData globals to be defined inline before this
// script loads (see dashboard.html).

document.addEventListener("DOMContentLoaded", function () {
  const palette = {
    sales: "#4f46e5",
    expenses: "#dc2626",
    products: ["#4f46e5", "#16a34a", "#d97706", "#0891b2", "#db2777", "#9333ea", "#65a30d"],
    status: { Paid: "#16a34a", "Partially Paid": "#d97706", Pending: "#dc2626" },
  };

  const seCanvas = document.getElementById("salesExpensesChart");
  if (seCanvas) {
    new Chart(seCanvas, {
      type: "line",
      data: {
        labels: chartLabels,
        datasets: [
          { label: "Sales", data: chartSales, borderColor: palette.sales, backgroundColor: palette.sales, tension: 0.3 },
          { label: "Expenses", data: chartExpenses, borderColor: palette.expenses, backgroundColor: palette.expenses, tension: 0.3 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
  }

  const prodCanvas = document.getElementById("productChart");
  if (prodCanvas) {
    if (productLabels.length === 0) {
      prodCanvas.replaceWith(Object.assign(document.createElement("p"), { textContent: "No sales yet.", className: "empty-state" }));
    } else {
      new Chart(prodCanvas, {
        type: "bar",
        data: {
          labels: productLabels,
          datasets: [{ label: "Revenue", data: productValues, backgroundColor: palette.products }],
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
      });
    }
  }

  const statusCanvas = document.getElementById("statusChart");
  if (statusCanvas) {
    const labels = Object.keys(statusData);
    const values = Object.values(statusData);
    if (values.reduce((a, b) => a + b, 0) === 0) {
      statusCanvas.replaceWith(Object.assign(document.createElement("p"), { textContent: "No orders yet.", className: "empty-state" }));
    } else {
      new Chart(statusCanvas, {
        type: "doughnut",
        data: {
          labels: labels,
          datasets: [{ data: values, backgroundColor: labels.map((l) => palette.status[l] || "#999") }],
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
      });
    }
  }
});
