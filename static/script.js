document.addEventListener("DOMContentLoaded", () => {
    const jobList = document.getElementById("job-list");
    const modal = document.getElementById("applyModal");
    const closeBtn = document.querySelector(".close");
    const form = document.getElementById("applyForm");

    const resultModal = document.getElementById("resultModal");
    const resultMessage = document.getElementById("resultMessage");
    const okBtn = document.getElementById("okBtn");

    // Load jobs
    fetch("/jobs")
        .then(res => res.json())
        .then(data => {
            const jobs = data.jobs || [];
            if (jobs.length === 0) {
                jobList.innerHTML = `<tr><td colspan="3">No jobs available right now.</td></tr>`;
                return;
            }

            jobs.forEach(job => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${job.title}</td>
                    <td>${job.location}</td>
                    <td><button class="btn apply-btn" data-jobid="${job.id}">Apply</button></td>
                `;
                jobList.appendChild(row);
            });

            // Bind Apply buttons
            document.querySelectorAll(".apply-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    document.getElementById("job_id").value = btn.dataset.jobid;
                    form.action = `/apply/${btn.dataset.jobid}`;
                    modal.style.display = "block";
                });
            });
        })
        .catch(err => {
            jobList.innerHTML = `<tr><td colspan="3">Error loading jobs</td></tr>`;
            console.error(err);
        });

    // Close modal
    closeBtn.onclick = () => modal.style.display = "none";
    window.onclick = (e) => {
        if (e.target === modal) modal.style.display = "none";
        if (e.target === resultModal) resultModal.style.display = "none";
    };

    // Handle form submit
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const formData = new FormData(form);

        try {
            const res = await fetch(form.action, { method: "POST", body: formData });
            if (!res.ok) {
                const err = await res.json();
                resultMessage.innerText = "Application failed: " + (err.detail || "Unknown error");
            } else {
                resultMessage.innerText = "Applied successfully!";
            }
        } catch (err) {
            resultMessage.innerText = "Application failed: " + err.message;
        }

        modal.style.display = "none";
        resultModal.style.display = "block";
    });

    okBtn.addEventListener("click", () => {
        resultModal.style.display = "none";
        window.location.href = "/"; // back to job listing
    });
});
