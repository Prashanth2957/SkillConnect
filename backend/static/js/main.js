function analyzeResume() {
  let resume = document.getElementById("resume").value;

  fetch("/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: "resume=" + encodeURIComponent(resume)
  })
  .then(response => response.json())
  .then(data => {
    document.getElementById("result").innerHTML = `
      <h3>Suggested Role: ${data.job_role}</h3>
      <p>Expected Salary: ${data.salary}</p>
      <p>Recommended Courses:</p>
      <ul>
        ${data.courses.map(c => `<li>${c}</li>`).join("")}
      </ul>
    `;
  })
  .catch(error => {
    document.getElementById("result").innerHTML =
      "<p style='color:red'>Error getting result</p>";
    console.error(error);
  });
}

