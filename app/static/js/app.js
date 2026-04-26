document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("canvas[data-chart]").forEach((canvas) => {
    try {
      const payload = JSON.parse(canvas.dataset.chart);
      const config = {
        type: payload.type || "bar",
        data: {
          labels: payload.labels || [],
          datasets: payload.datasets || [{
            label: payload.label || "",
            data: payload.values || [],
            borderWidth: 2,
            tension: 0.35,
            fill: payload.type === 'line',
            backgroundColor: payload.backgroundColor || [
              'rgba(15,81,50,.85)','rgba(183,138,43,.85)','rgba(28,98,63,.75)','rgba(145,117,47,.8)','rgba(91,114,101,.8)','rgba(13,110,253,.7)'
            ],
            borderColor: payload.borderColor || 'rgba(15,81,50,1)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: payload.type !== 'bar' || (payload.label && payload.label.length > 0) } },
          scales: payload.type === 'doughnut' ? {} : {
            y: { beginAtZero: true, ticks: { precision: 0 } },
            x: { ticks: { autoSkip: false, maxRotation: 0, minRotation: 0 } }
          }
        }
      };
      new Chart(canvas, config);
    } catch (e) {
      console.error('Chart render failed', e);
    }
  });

  const statusSelect = document.querySelector('[data-toggle-closure]');
  const closureBox = document.querySelector('[data-closure-box]');
  const obsType = document.querySelector('[data-toggle-observation-type]');
  const criterionBox = document.querySelector('[data-criterion-box]');
  const escalatedCheck = document.querySelector('[data-toggle-escalation]');
  const escalationBox = document.querySelector('[data-escalation-box]');

  function syncConditionalFields(){
    if (statusSelect && closureBox) closureBox.style.display = statusSelect.value === 'closed' ? 'block' : 'none';
    if (obsType && criterionBox) criterionBox.style.display = obsType.value === 'criterion' ? 'block' : 'none';
    if (escalatedCheck && escalationBox) escalationBox.style.display = escalatedCheck.checked ? 'block' : 'none';
  }
  [statusSelect, obsType, escalatedCheck].forEach(el => { if(el){ el.addEventListener('change', syncConditionalFields); } });
  syncConditionalFields();
});
