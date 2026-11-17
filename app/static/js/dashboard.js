/**
 * Smart Supermarket - Dashboard Analytics Chart.js Engine
 */

let salesChartInstance = null;
let categoryChartInstance = null;

document.addEventListener('DOMContentLoaded', () => {
    initDashboardCharts('daily');

    // Chart period filter switch buttons (daily, monthly)
    const filterBtns = document.querySelectorAll('[data-chart-period]');
    filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            filterBtns.forEach(b => b.classList.remove('active', 'btn-primary'));
            filterBtns.forEach(b => b.classList.add('btn-outline-secondary'));

            btn.classList.add('active', 'btn-primary');
            btn.classList.remove('btn-outline-secondary');

            const period = btn.getAttribute('data-chart-period');
            fetchChartData(period);
        });
    });
});

function initDashboardCharts(period = 'daily') {
    fetchChartData(period);
}

function fetchChartData(period) {
    fetch(`/api/dashboard/charts?period=${period}`)
        .then(res => res.json())
        .then(data => {
            renderSalesChart(data.sales_chart);
            renderCategoryChart(data.category_chart);
        })
        .catch(err => {
            console.error("Dashboard chart fetch error:", err);
        });
}

function renderSalesChart(chartData) {
    const ctx = document.getElementById('salesTrendsChart');
    if (!ctx) return;

    if (salesChartInstance) {
        salesChartInstance.destroy();
    }

    salesChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: [
                {
                    label: 'Gross Revenue ($)',
                    data: chartData.sales,
                    backgroundColor: 'rgba(37, 99, 235, 0.85)',
                    borderRadius: 6,
                    borderSkipped: false
                },
                {
                    label: 'Gross Profit ($)',
                    data: chartData.profit,
                    backgroundColor: 'rgba(16, 185, 129, 0.85)',
                    borderRadius: 6,
                    borderSkipped: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        boxWidth: 12,
                        font: { family: 'Inter', size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: $${context.raw.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(val) { return '$' + val; }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    grid: { display: false }
                }
            }
        }
    });
}

function renderCategoryChart(categoryData) {
    const ctx = document.getElementById('categoryPieChart');
    if (!ctx) return;

    if (categoryChartInstance) {
        categoryChartInstance.destroy();
    }

    const palette = [
        '#2563eb', '#10b981', '#f59e0b', '#8b5cf6', 
        '#ec4899', '#06b6d4', '#84cc16', '#64748b'
    ];

    categoryChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: categoryData.labels,
            datasets: [{
                data: categoryData.data,
                backgroundColor: palette.slice(0, categoryData.labels.length),
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 10,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.label}: $${context.raw.toFixed(2)}`;
                        }
                    }
                }
            },
            cutout: '70%'
        }
    });
}
