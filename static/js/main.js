
document.addEventListener("DOMContentLoaded", function(){
  const quickBtn = document.getElementById("quick-add-btn");
  const quickModal = new bootstrap.Modal(document.getElementById("quickAddModal"));
  quickBtn.addEventListener("click", ()=> quickModal.show());
  document.getElementById("quickClose").addEventListener("click", ()=> quickModal.hide());

  const quickForm = document.getElementById("quickAddForm");
  quickForm.addEventListener("submit", function(e){
    e.preventDefault();
    const data = new FormData(quickForm);
    fetch("/add", { method:"POST", body: data }).then(r=>{
      if(r.redirected){ window.location.href = r.url; } else { quickModal.hide(); refreshAll(); }
    });
  });

  // Charts
  let pieChart=null, barChart=null;
  function initCharts(){
    const pieCtx = document.getElementById("pieChart").getContext("2d");
    const barCtx = document.getElementById("barChart").getContext("2d");
    pieChart = new Chart(pieCtx, { type:'pie', data: { labels:[], datasets:[{data:[], backgroundColor:[]}] }, options:{} });
    barChart = new Chart(barCtx, { type:'bar', data: { labels:[], datasets:[{label:'Income', data:[]},{label:'Expense', data:[]}], }, options:{responsive:true} });
  }

  function refreshAll(){
    fetch("/api/summary").then(r=>r.json()).then(j=>{
      // animate numbers simply
      document.getElementById("sum-income").innerText = j.Income || 0;
      document.getElementById("sum-expense").innerText = j.Expense || 0;
      document.getElementById("sum-invest").innerText = j.Investment || 0;
    });
    fetch("/api/chart_data").then(r=>r.json()).then(j=>{
      // pie
      const labels = j.expense_by_category.map(x=>x.category);
      const data = j.expense_by_category.map(x=>x.total);
      pieChart.data.labels = labels; pieChart.data.datasets[0].data = data;
      pieChart.data.datasets[0].backgroundColor = labels.map((_,i)=>['#e62429','#ffb86b','#66b2ff','#7efc5f','#d78cff'][i%5]);
      pieChart.update();
      // bar
      barChart.data.labels = j.monthly.labels;
      barChart.data.datasets[0].data = j.monthly.income;
      barChart.data.datasets[1].data = j.monthly.expense;
      barChart.update();
    });
  }

  initCharts();
  refreshAll();
  // poll every 5s for live updates
  setInterval(refreshAll, 5000);
});
