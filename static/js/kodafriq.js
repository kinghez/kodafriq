/* Kodafriq Interactive Scripting */
document.addEventListener('DOMContentLoaded', () => {
    // Render animated score gauges
    document.querySelectorAll('.kf-score-dial').forEach(dial => {
        const score = parseFloat(dial.dataset.score || 0);
        const circle = dial.querySelector('.kf-progress-circle');
        if (circle) {
            const radius = circle.r.baseVal.value;
            const circumference = 2 * Math.PI * radius;
            circle.style.strokeDasharray = `${circumference} ${circumference}`;
            const offset = circumference - (score / 100) * circumference;
            circle.style.strokeDashoffset = offset;
        }
    });

    // Auto-dismiss alerts
    document.querySelectorAll('.kf-alert-dismissible').forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-8px)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});
