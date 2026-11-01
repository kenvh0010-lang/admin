"use strict";
const $ = id => document.getElementById(id);
const rand = (a, b) => Math.floor(Math.random() * (b - a + 1)) + a;
const pick = arr => arr[Math.floor(Math.random() * arr.length)];
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const shuffle = arr => arr.map(v => [Math.random(), v]).sort((x, y) => x[0] - y[0]).map(x => x[1]);
const money = n => n.toLocaleString("vi-VN") + "đ";

const MAX_DAY = 30;
const DAILY_COST = 120000;
const MAX_APPLY_PER_DAY = 3;

let S = null; // trạng thái game
let chosenField = null;

/* ---------- Màn hình bắt đầu ---------- */
function setupStart() {
  const list = $("field-list");
  for (const [key, f] of Object.entries(FIELDS)) {
    const b = document.createElement("button");
    b.innerHTML = `${f.icon} <b>${f.name}</b><small>Kỹ năng chính: ${f.skill}</small>`;
    b.onclick = () => {
      chosenField = key;
      [...list.children].forEach(c => c.classList.remove("selected"));
      b.classList.add("selected");
      $("btn-start").disabled = false;
    };
    list.appendChild(b);
  }
  $("btn-start").onclick = startGame;
}

function startGame() {
  S = {
    name: $("inp-name").value.trim() || "Ứng viên",
    field: chosenField,
    day: 1, money: 3000000, energy: 100,
    skill: 20, cv: 20, confidence: 50, network: 0,
    appliedToday: 0, jobs: [], apps: [], nextId: 1,
  };
  refreshJobs();
  show("screen-game");
  log(`Chào ${S.name}! Hành trình tìm việc ngành ${FIELDS[S.field].name} bắt đầu.`);
  render();
}

function show(id) {
  document.querySelectorAll(".screen").forEach(s => s.classList.add("hidden"));
  $(id).classList.remove("hidden");
}

/* ---------- Việc làm ---------- */
function makeJob() {
  const c = pick(COMPANIES);
  const t = c.tier;
  return {
    id: S.nextId++, company: c.name, tier: t,
    role: pick(ROLES[S.field]),
    salary: (rand(7, 11) + t * 4 + rand(0, 3)) * 1000000,
    reqSkill: 20 + t * 15 + rand(-5, 5),
    reqCv: 15 + t * 15 + rand(-5, 5),
  };
}

function refreshJobs() {
  const applied = new Set(S.apps.map(a => a.job.id));
  S.jobs = S.jobs.filter(j => !applied.has(j.id)).slice(0, 1);
  while (S.jobs.length < 4) S.jobs.push(makeJob());
}

function interviewChance(job) {
  let p = 0.3 + (S.cv - job.reqCv) / 60 + (S.skill - job.reqSkill) / 120 + S.network / 150;
  return clamp(p, 0.05, 0.92);
}

function apply(jobId) {
  if (S.energy < 10 || S.appliedToday >= MAX_APPLY_PER_DAY) return;
  const job = S.jobs.find(j => j.id === jobId);
  S.jobs = S.jobs.filter(j => j.id !== jobId);
  S.energy -= 10;
  S.appliedToday++;
  S.apps.push({ job, status: "pending", replyDay: S.day + rand(1, 3), deadline: 0 });
  log(`Đã nộp đơn: ${job.role} – ${job.company}.`);
  render();
}

/* ---------- Hành động trong ngày ---------- */
const ACTIONS = [
  { id: "study", label: "📚 Tự học", desc: "+Kỹ năng, −15 năng lượng", energy: 15,
    run: () => { const g = rand(4, 7); S.skill += g; return `Bạn tự học ${FIELDS[S.field].skill}. Kỹ năng +${g}.`; } },
  { id: "course", label: "🎓 Học khoá online", desc: "+Nhiều kỹ năng, −700.000đ, −20 năng lượng", energy: 20, cost: 700000,
    run: () => { const g = rand(10, 14); S.skill += g; return `Hoàn thành một khoá học. Kỹ năng +${g}.`; } },
  { id: "cv", label: "📝 Sửa CV & portfolio", desc: "+CV, −10 năng lượng", energy: 10,
    run: () => { const g = rand(8, 12); S.cv += g; return `CV gọn gàng, ấn tượng hơn. CV +${g}.`; } },
  { id: "network", label: "🤝 Đi sự kiện networking", desc: "+Quan hệ, −200.000đ, −15 năng lượng", energy: 15, cost: 200000,
    run: () => { const g = rand(8, 14); S.network += g; S.confidence += 3; return `Bạn quen thêm vài người trong ngành. Quan hệ +${g}.`; } },
  { id: "work", label: "🛵 Làm thêm", desc: "+600.000đ, −30 năng lượng", energy: 30,
    run: () => { const g = rand(5, 7) * 100000; S.money += g; return `Làm thêm kiếm được ${money(g)}.`; } },
  { id: "rest", label: "😴 Nghỉ ngơi", desc: "+40 năng lượng, +tự tin", energy: 0,
    run: () => { S.energy += 40; S.confidence += 5; return "Ngủ một giấc thật ngon. Năng lượng hồi phục."; } },
];

function doAction(a) {
  if (S.energy < a.energy || (a.cost && S.money < a.cost)) return;
  S.energy -= a.energy;
  if (a.cost) S.money -= a.cost;
  log(a.run(), "good");
  endDay();
}

function endDay() {
  S.money -= DAILY_COST;
  S.day++;
  S.appliedToday = 0;

  // Phản hồi đơn ứng tuyển
  for (const app of S.apps) {
    if (app.status === "pending" && S.day >= app.replyDay) {
      if (Math.random() < interviewChance(app.job)) {
        app.status = "interview";
        app.deadline = S.day + 3;
        log(`📩 ${app.job.company} mời bạn phỏng vấn vị trí ${app.job.role}! (hạn: ngày ${app.deadline})`, "good");
      } else {
        app.status = "rejected";
        S.confidence -= 3;
        log(`✉️ ${app.job.company} đã từ chối hồ sơ của bạn.`, "bad");
      }
    } else if (app.status === "interview" && S.day > app.deadline) {
      app.status = "missed";
      log(`⌛ Bạn đã lỡ buổi phỏng vấn với ${app.job.company}.`, "bad");
    }
  }

  // Sự kiện ngẫu nhiên
  if (Math.random() < 0.25) {
    const e = pick(EVENTS);
    e.fx(S);
    log("🎲 " + e.text);
  }

  if (S.day % 3 === 1) { refreshJobs(); log("🆕 Bảng tin tuyển dụng có tin mới."); }
  normalize();

  if (S.money < 0) return gameOver("💸", "Hết tiền!", "Bạn không còn đủ tiền trang trải cuộc sống và phải về quê nghỉ ngơi. Lần sau hãy cân đối giữa làm thêm và tìm việc nhé.");
  if (S.day > MAX_DAY) return gameOver("📅", "Hết thời gian!", "30 ngày đã trôi qua mà chưa có offer. Đừng nản — mỗi lần từ chối là một bài học.");
  render();
}

function normalize() {
  S.energy = clamp(S.energy, 0, 100);
  S.confidence = clamp(S.confidence, 0, 100);
  S.skill = clamp(S.skill, 0, 100);
  S.cv = clamp(S.cv, 0, 100);
  S.network = clamp(S.network, 0, 100);
}

/* ---------- Phỏng vấn ---------- */
let IV = null;

function startInterview(app) {
  if (S.energy < 20) return;
  S.energy -= 20;
  const qs = shuffle(COMMON_QUESTIONS).slice(0, 2).concat(shuffle(FIELD_QUESTIONS[S.field]).slice(0, 2));
  IV = { app, qs: shuffle(qs), i: 0, score: 0 };
  $("iv-title").textContent = `Phỏng vấn: ${app.job.role} – ${app.job.company}`;
  show("screen-interview");
  showQuestion();
}

function showQuestion() {
  const q = IV.qs[IV.i];
  $("iv-progress").textContent = `Câu ${IV.i + 1}/${IV.qs.length}`;
  $("iv-question").textContent = "🧑‍💼 " + q.q;
  $("iv-feedback").textContent = "";
  const box = $("iv-answers");
  box.innerHTML = "";
  for (const [text, score] of shuffle(q.a)) {
    const b = document.createElement("button");
    b.textContent = text;
    b.onclick = () => answer(score);
    box.appendChild(b);
  }
}

function answer(score) {
  IV.score += score;
  S.confidence += score === 2 ? 3 : score === 0 ? -4 : 0;
  [...$("iv-answers").children].forEach(b => b.disabled = true);
  const fb = ["Nhà tuyển dụng nhíu mày… 😬", "Nhà tuyển dụng gật gù. 🙂", "Nhà tuyển dụng tỏ ra rất ấn tượng! 🤩"][score];
  $("iv-feedback").textContent = fb;
  setTimeout(() => {
    IV.i++;
    if (IV.i < IV.qs.length) showQuestion(); else finishInterview();
  }, 900);
}

function finishInterview() {
  const job = IV.app.job;
  normalize();
  const answerPart = IV.score / (IV.qs.length * 2) * 45;
  const skillPart = Math.min(S.skill / job.reqSkill, 1.1) * 40;
  const confPart = S.confidence / 10;
  const tired = S.energy < 20 ? -8 : 0;
  const total = Math.round(answerPart + skillPart + confPart + tired);
  const need = 75 + job.tier * 5;

  show("screen-game");
  if (total >= need) {
    IV.app.status = "offer";
    return gameOver("🎉", "Bạn đã nhận được offer!",
      `${job.company} chào đón ${S.name} vào vị trí <b>${job.role}</b> với mức lương <b>${money(job.salary)}/tháng</b>.<br>` +
      `Hoàn thành trong ${S.day} ngày · Điểm phỏng vấn ${total}/${need} · Tiền còn lại ${money(S.money)}.`);
  }
  IV.app.status = "failed";
  S.confidence -= 8;
  log(`❌ Trượt phỏng vấn ${job.company} (điểm ${total}, cần ${need}). ` +
      (S.skill < job.reqSkill ? "Kỹ năng chưa đủ yêu cầu." : "Hãy chuẩn bị câu trả lời kỹ hơn."), "bad");
  endDay();
}

/* ---------- Kết thúc ---------- */
function gameOver(emoji, title, text) {
  $("end-emoji").textContent = emoji;
  $("end-title").textContent = title;
  $("end-text").innerHTML = text;
  show("screen-end");
}

/* ---------- Hiển thị ---------- */
function log(text, cls = "") {
  const li = document.createElement("li");
  li.className = cls;
  li.textContent = `Ngày ${S.day}: ${text}`;
  $("log").prepend(li);
}

function stat(label, value, pct) {
  return `<div class="stat"><span>${label}</span><b>${value}</b>${pct != null ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ""}</div>`;
}

function render() {
  $("stats").innerHTML =
    stat("📅 Ngày", `${S.day}/${MAX_DAY}`, S.day / MAX_DAY * 100) +
    stat("💰 Tiền", money(S.money)) +
    stat("⚡ Năng lượng", S.energy, S.energy) +
    stat(`🧠 ${FIELDS[S.field].skill}`, S.skill, S.skill) +
    stat("📝 CV", S.cv, S.cv) +
    stat("💪 Tự tin", S.confidence, S.confidence) +
    stat("🤝 Quan hệ", S.network, S.network);

  const acts = $("actions");
  acts.innerHTML = "";
  for (const a of ACTIONS) {
    const b = document.createElement("button");
    b.innerHTML = `${a.label}<small>${a.desc}</small>`;
    b.disabled = S.energy < a.energy || (a.cost && S.money < a.cost);
    b.onclick = () => doAction(a);
    acts.appendChild(b);
  }

  const jobs = $("jobs");
  jobs.innerHTML = "";
  const canApply = S.energy >= 10 && S.appliedToday < MAX_APPLY_PER_DAY;
  for (const j of S.jobs) {
    const li = document.createElement("li");
    li.innerHTML = `<div class="row"><div><b>${j.role}</b><br><span class="muted">${j.company}</span></div>
      <button ${canApply ? "" : "disabled"}>Nộp đơn (−10⚡)</button></div>
      <span class="tag">${"★".repeat(j.tier)}</span><span class="tag">${money(j.salary)}</span>
      <span class="tag">Kỹ năng ≥ ${j.reqSkill}</span><span class="tag">CV ≥ ${j.reqCv}</span>
      <span class="tag">Cơ hội PV ~${Math.round(interviewChance(j) * 100)}%</span>`;
    li.querySelector("button").onclick = () => apply(j.id);
    jobs.appendChild(li);
  }
  if (!S.jobs.length) jobs.innerHTML = `<li class="muted">Chưa có tin mới. Quay lại sau vài ngày.</li>`;
  jobs.insertAdjacentHTML("beforeend", `<li class="muted">Đã nộp hôm nay: ${S.appliedToday}/${MAX_APPLY_PER_DAY}</li>`);

  const apps = $("apps");
  apps.innerHTML = "";
  const label = { pending: "⏳ Đang chờ phản hồi", interview: "📩 Được mời phỏng vấn", rejected: "✉️ Bị từ chối",
                  failed: "❌ Trượt phỏng vấn", missed: "⌛ Lỡ phỏng vấn", offer: "🎉 Offer" };
  for (const app of [...S.apps].reverse()) {
    const li = document.createElement("li");
    li.className = "st-" + app.status;
    li.innerHTML = `<b>${app.job.role}</b> – ${app.job.company}<br><span class="muted">${label[app.status]}</span>`;
    if (app.status === "interview") {
      const b = document.createElement("button");
      b.className = "primary";
      b.style.marginTop = "8px";
      b.textContent = `Đi phỏng vấn (−20⚡, hạn ngày ${app.deadline})`;
      b.disabled = S.energy < 20;
      b.onclick = () => startInterview(app);
      li.appendChild(b);
    }
    apps.appendChild(li);
  }
  if (!S.apps.length) apps.innerHTML = `<li class="muted">Bạn chưa nộp đơn nào.</li>`;
}

setupStart();
