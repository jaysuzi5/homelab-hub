function renderDartChart(canvasId, scores) {
    // Bar colors based on thresholds
    const barColors = scores.map(score => {
        if (score < 39.5) return 'rgba(239,68,68,0.8)';   // red
        if (score < 59.5) return 'rgba(234,179,8,0.8)';   // yellow
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
