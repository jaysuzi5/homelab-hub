function renderDartChart(canvasId, scores) {
    // Bar colors based on thresholds
    const barColors = scores.map(score => {
        if (score < 34.5) return 'rgba(239,68,68,0.8)';   // red
        if (score < 49.5) return 'rgba(234,179,8,0.8)';   // yellow
        return 'rgba(34,197,94,0.8)';                     // green
    });

    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: scores.map(() => ''), // no labels, just bars
            datasets: [{
                label: 'Avg 3 Dart Score',
                data: scores,
                backgroundColor: barColors,
                borderColor: barColors.map(c => c.replace('0.8','1')),
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { ticks: { display: false }, grid: { drawTicks: false, drawBorder: false } },
                y: { title: { display: true, text: 'Average 3 Dart Score' }, beginAtZero: true }
            },
            plugins: {
                legend: { display: false },
                tooltip: { enabled: true },
                datalabels: { enabled: false }
            }
        }
    });
}


function renderEmporiaUsageChart(canvasId, metrics) {
    const labels = metrics.map(m => m.date);
    const usage = metrics.map(m => m.usage);

    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '',  // empty label
                data: usage,
                fill: true,
                borderColor: 'rgba(34,197,94,1)',
                backgroundColor: 'rgba(34,197,94,0.2)',
                tension: 0.2,
                pointRadius: 4,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: { display: true, text: 'Date' }
                },
                y: {
                    title: { display: true, text: 'kWh' },
                    beginAtZero: true
                }
            },
            plugins: {
                legend: { display: false },    // 🔹 now correctly hides the rectangle
                tooltip: { enabled: true }   // optional
            }
        }        
    });
}
