/* ═══════════════════════════════════════════════════════════
   FinanceAI — CRED-Inspired Dashboard JavaScript
   Gold-themed Chart.js charts with dark backgrounds
   ═══════════════════════════════════════════════════════════ */

// ─── Chart.js Global Config ────────────────────────────────
Chart.defaults.color = '#666666';
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.04)';
Chart.defaults.font.family = "'Poppins', sans-serif";
Chart.defaults.font.weight = '400';
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.padding = 20;

// ─── CRED Color Palette ────────────────────────────────────
const COLORS = {
    gold:   { bg: 'rgba(212, 175, 55, 0.15)', border: '#D4AF37', solid: 'rgba(212, 175, 55, 0.5)' },
    green:  { bg: 'rgba(46, 204, 113, 0.12)', border: '#2ECC71', solid: 'rgba(46, 204, 113, 0.5)' },
    blue:   { bg: 'rgba(52, 152, 219, 0.12)', border: '#3498DB', solid: 'rgba(52, 152, 219, 0.5)' },
    orange: { bg: 'rgba(230, 126, 34, 0.12)', border: '#E67E22', solid: 'rgba(230, 126, 34, 0.5)' },
    red:    { bg: 'rgba(231, 76, 60, 0.12)', border: '#E74C3C', solid: 'rgba(231, 76, 60, 0.5)' },
    white:  { bg: 'rgba(255, 255, 255, 0.05)', border: '#FFFFFF', solid: 'rgba(255, 255, 255, 0.3)' },
};

const CATEGORY_COLORS = {
    'Food':     COLORS.orange,
    'Travel':   COLORS.blue,
    'Shopping': COLORS.gold,
    'Bills':    COLORS.green,
};

const TOOLTIP_STYLE = {
    backgroundColor: 'rgba(26, 26, 26, 0.96)',
    borderColor: 'rgba(212, 175, 55, 0.2)',
    borderWidth: 1,
    cornerRadius: 10,
    padding: 14,
    titleFont: { weight: '600', size: 13 },
    bodyFont: { size: 12 },
    titleColor: '#FFFFFF',
    bodyColor: '#A0A0A0',
};

// ─── Load Dashboard Charts ─────────────────────────────────
function loadDashboardCharts() {
    loadMonthlyChart();
    loadCategoryChart();
}

async function loadMonthlyChart() {
    const canvas = document.getElementById('monthlyChart');
    if (!canvas) return;

    try {
        const response = await fetch('/api/monthly_data');
        const data = await response.json();

        const labels = data.map(d => {
            const [year, month] = d.month.split('-');
            return new Date(year, month - 1).toLocaleDateString('en-IN', {
                month: 'short', year: '2-digit'
            });
        });
        const values = data.map(d => d.total);

        new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Monthly Spending (₹)',
                    data: values,
                    borderColor: COLORS.gold.border,
                    backgroundColor: createGoldGradient(canvas),
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.45,
                    pointBackgroundColor: COLORS.gold.border,
                    pointBorderColor: '#1A1A1A',
                    pointBorderWidth: 3,
                    pointRadius: 5,
                    pointHoverRadius: 9,
                    pointHoverBorderWidth: 3,
                    pointHoverBackgroundColor: '#E8C547',
                    pointHoverBorderColor: '#1A1A1A',
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        ...TOOLTIP_STYLE,
                        callbacks: {
                            label: (ctx) => `  ₹${ctx.parsed.y.toLocaleString('en-IN')}`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: {
                            color: '#4A4A4A',
                            font: { size: 11 },
                            callback: (val) => '₹' + (val / 1000).toFixed(0) + 'K'
                        }
                    },
                    x: {
                        grid: { display: false },
                        ticks: {
                            color: '#4A4A4A',
                            font: { size: 11 },
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Error loading monthly chart:', err);
    }
}

async function loadCategoryChart() {
    const canvas = document.getElementById('categoryChart');
    if (!canvas) return;

    try {
        const response = await fetch('/api/category_data');
        const data = await response.json();

        const labels = data.map(d => d.category);
        const values = data.map(d => d.total);
        const bgColors = labels.map(l => (CATEGORY_COLORS[l] || COLORS.gold).solid);
        const borderColors = labels.map(l => (CATEGORY_COLORS[l] || COLORS.gold).border);

        new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: bgColors,
                    borderColor: '#1A1A1A',
                    borderWidth: 3,
                    hoverOffset: 8,
                    spacing: 3,
                    hoverBorderColor: borderColors,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '68%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 18,
                            color: '#A0A0A0',
                            font: { size: 12, weight: '500', family: "'Poppins', sans-serif" },
                        }
                    },
                    tooltip: {
                        ...TOOLTIP_STYLE,
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = ((ctx.parsed / total) * 100).toFixed(1);
                                return `  ₹${ctx.parsed.toLocaleString('en-IN')} (${pct}%)`;
                            }
                        }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Error loading category chart:', err);
    }
}

// ─── Comparison Chart (Analytics Page) ─────────────────────
function loadComparisonChart(monthlyData) {
    const canvas = document.getElementById('comparisonChart');
    if (!canvas || !monthlyData) return;

    const labels = monthlyData.map(d => {
        const [year, month] = d.month.split('-');
        return new Date(year, month - 1).toLocaleDateString('en-IN', {
            month: 'short', year: '2-digit'
        });
    });
    const values = monthlyData.map(d => d.amount);

    // Gold for all bars, but highlight increases/decreases with subtle tones
    const bgColors = values.map((val, i) => {
        if (i === 0) return COLORS.gold.solid;
        return val > values[i - 1]
            ? COLORS.red.solid
            : COLORS.green.solid;
    });
    const borderColors = values.map((val, i) => {
        if (i === 0) return COLORS.gold.border;
        return val > values[i - 1] ? COLORS.red.border : COLORS.green.border;
    });

    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Monthly Spending (₹)',
                data: values, 
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1.5,
                borderRadius: 8,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    ...TOOLTIP_STYLE,
                    callbacks: {
                        label: (ctx) => `  ₹${ctx.parsed.y.toLocaleString('en-IN')}`,
                        afterLabel: (ctx) => {
                            if (ctx.dataIndex === 0) return '';
                            const prev = values[ctx.dataIndex - 1];
                            const diff = ctx.parsed.y - prev;
                            const pct = ((diff / prev) * 100).toFixed(1);
                            const sign = diff > 0 ? '+' : '';
                            return `  ${sign}${pct}% vs previous month`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: {
                        color: '#4A4A4A',
                        font: { size: 11 },
                        callback: (val) => '₹' + (val / 1000).toFixed(0) + 'K'
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#4A4A4A',
                        font: { size: 11 },
                    }
                }
            }
        }
    });
}

// ─── Gradient Helpers ──────────────────────────────────────
function createGoldGradient(canvas) {
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, 320);
    gradient.addColorStop(0, 'rgba(212, 175, 55, 0.25)');
    gradient.addColorStop(0.5, 'rgba(212, 175, 55, 0.08)');
    gradient.addColorStop(1, 'rgba(212, 175, 55, 0.0)');
    return gradient;
}

// ─── Mobile Nav Toggle ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const toggle = document.getElementById('nav-toggle');
    const links = document.getElementById('nav-links');

    if (toggle && links) {
        toggle.addEventListener('click', () => {
            links.classList.toggle('active');
            toggle.textContent = links.classList.contains('active') ? '✕' : '☰';
        });
    }

    // Auto-dismiss flash messages after 5s
    document.querySelectorAll('.flash').forEach((flash) => {
        setTimeout(() => {
            flash.style.opacity = '0';
            flash.style.transform = 'translateY(-10px)';
            flash.style.transition = 'all 0.4s ease';
            setTimeout(() => flash.remove(), 400);
        }, 5000);
    });
});
