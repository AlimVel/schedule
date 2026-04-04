<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GoShiet — README</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Manrope:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --purple: #7c3aed;
    --purple-light: #a78bfa;
    --purple-mid: #8b5cf6;
    --purple-pale: #ede9fe;
    --purple-pale2: #f5f3ff;
    --purple-border: rgba(139, 92, 246, 0.2);
    --purple-border-bright: rgba(139, 92, 246, 0.45);
    --bg: #fafafa;
    --surface: #ffffff;
    --surface2: #f9f8ff;
    --border: #e8e5f0;
    --text: #1a1625;
    --text-muted: #6b6480;
    --text-dim: #a89fc0;
    --mono: 'Space Mono', monospace;
    --sans: 'Manrope', sans-serif;
  }

  body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    line-height: 1.7;
    overflow-x: hidden;
  }

  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image: radial-gradient(circle, rgba(139,92,246,0.11) 1px, transparent 1px);
    background-size: 32px 32px;
    pointer-events: none;
    z-index: 0;
  }

  .wrapper {
    max-width: 900px;
    margin: 0 auto;
    padding: 0 2rem 6rem;
    position: relative;
    z-index: 1;
  }

  .hero {
    text-align: center;
    padding: 7rem 0 5rem;
    position: relative;
  }

  .hero-glow {
    position: absolute;
    top: 40%; left: 50%;
    transform: translate(-50%, -55%);
    width: 700px; height: 320px;
    background: radial-gradient(ellipse, rgba(167,139,250,0.22) 0%, transparent 68%);
    pointer-events: none;
    animation: pulse-glow 5s ease-in-out infinite;
  }

  @keyframes pulse-glow {
    0%, 100% { opacity: 0.7; transform: translate(-50%, -55%) scale(1); }
    50%       { opacity: 1;   transform: translate(-50%, -55%) scale(1.07); }
  }

  .logo-line {
    font-family: var(--mono);
    font-size: clamp(3rem, 9vw, 5.8rem);
    font-weight: 700;
    letter-spacing: -2px;
    line-height: 1;
    position: relative;
  }

  .logo-go    { color: #1a1625; animation: fade-up 0.7s ease both; }
  .logo-shiet {
    color: var(--purple);
    text-shadow: 0 2px 24px rgba(124,58,237,0.25);
    animation: fade-up 0.7s 0.08s ease both;
  }

  @keyframes fade-up {
    from { opacity: 0; transform: translateY(18px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .hero-tagline {
    font-size: 0.78rem;
    color: var(--purple-mid);
    letter-spacing: 0.22em;
    text-transform: uppercase;
    font-weight: 600;
    margin-top: 1.4rem;
    animation: fade-up 0.7s 0.16s ease both;
  }

  .hero-desc {
    font-size: 1.05rem;
    color: var(--text-muted);
    max-width: 540px;
    margin: 1.6rem auto 0;
    font-weight: 400;
    animation: fade-up 0.7s 0.24s ease both;
  }

  .badges {
    display: flex;
    gap: 0.55rem;
    justify-content: center;
    margin-top: 2.4rem;
    flex-wrap: wrap;
    animation: fade-up 0.7s 0.32s ease both;
  }

  .badge {
    font-family: var(--mono);
    font-size: 0.68rem;
    padding: 0.32rem 0.85rem;
    border-radius: 100px;
    border: 1.5px solid var(--purple-border-bright);
    background: var(--purple-pale);
    color: var(--purple);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    font-weight: 700;
    transition: background 0.2s, color 0.2s;
  }

  .badge:hover { background: var(--purple); color: #fff; }

  .divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--purple-border-bright), transparent);
    margin: 4rem 0;
  }

  .section-label {
    font-family: var(--mono);
    font-size: 0.67rem;
    color: var(--purple-mid);
    letter-spacing: 0.22em;
    text-transform: uppercase;
    margin-bottom: 0.55rem;
  }

  .section-title {
    font-size: 1.85rem;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 1.8rem;
    letter-spacing: -0.5px;
  }

  .roles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 0.9rem;
  }

  .role-card {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 14px;
    padding: 1.5rem 1.2rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.22s, transform 0.22s, box-shadow 0.22s;
  }

  .role-card::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--purple-pale2) 0%, transparent 60%);
    opacity: 0;
    transition: opacity 0.22s;
    border-radius: inherit;
  }

  .role-card:hover {
    border-color: var(--purple-border-bright);
    transform: translateY(-3px);
    box-shadow: 0 10px 32px rgba(124,58,237,0.1);
  }

  .role-card:hover::after { opacity: 1; }
  .role-card > * { position: relative; z-index: 1; }

  .role-icon  { font-size: 1.7rem; margin-bottom: 0.75rem; }
  .role-title { font-weight: 700; font-size: 0.93rem; color: var(--text); margin-bottom: 0.45rem; }
  .role-desc  { font-size: 0.81rem; color: var(--text-muted); line-height: 1.6; }

  .modules-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 0.9rem;
  }

  .module-card {
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 14px;
    padding: 1.7rem 1.4rem;
    transition: border-color 0.22s, box-shadow 0.22s;
  }

  .module-card:hover {
    border-color: var(--purple-border-bright);
    box-shadow: 0 8px 28px rgba(124,58,237,0.09);
  }

  .module-number {
    font-family: var(--mono);
    font-size: 0.63rem;
    color: var(--purple-light);
    letter-spacing: 0.18em;
    margin-bottom: 0.8rem;
  }

  .module-title { font-size: 1.05rem; font-weight: 700; color: var(--text); margin-bottom: 1rem; }

  .module-features { list-style: none; }

  .module-features li {
    font-size: 0.84rem;
    color: var(--text-muted);
    padding: 0.32rem 0;
    border-bottom: 1px solid #f0eef8;
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .module-features li::before {
    content: '→';
    color: var(--purple-mid);
    flex-shrink: 0;
    font-family: var(--mono);
    font-size: 0.73rem;
    margin-top: 3px;
  }

  .module-features li:last-child { border-bottom: none; }

  .terminal {
    background: #1e1630;
    border: 1.5px solid #2e2448;
    border-radius: 12px;
    overflow: hidden;
    margin-top: 1.4rem;
  }

  .terminal-bar {
    background: #281e3e;
    border-bottom: 1px solid #2e2448;
    padding: 0.6rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }

  .dot   { width: 10px; height: 10px; border-radius: 50%; }
  .dot-r { background: #ff5f57; }
  .dot-y { background: #ffbd2e; }
  .dot-g { background: #28ca41; }

  .terminal-body {
    padding: 1.2rem 1.5rem;
    font-family: var(--mono);
    font-size: 0.81rem;
    line-height: 2;
    color: #a79dc8;
  }

  .terminal-body .cmd     { color: #c4b5fd; }
  .terminal-body .out     { color: #6ee7b7; }
  .terminal-body .comment { color: #4a3f6b; }

  .stack-row { display: flex; gap: 0.7rem; flex-wrap: wrap; margin-top: 1.4rem; }

  .stack-pill {
    font-family: var(--mono);
    font-size: 0.78rem;
    padding: 0.45rem 1rem;
    border-radius: 100px;
    border: 1.5px solid var(--purple-border-bright);
    background: var(--purple-pale);
    color: var(--purple);
    font-weight: 700;
    transition: background 0.2s, color 0.2s;
  }

  .stack-pill:hover { background: var(--purple); color: #fff; }

  .team-grid { display: grid; gap: 0.55rem; margin-top: 1.4rem; }

  .team-row {
    display: grid;
    grid-template-columns: 2rem 1fr auto;
    align-items: center;
    gap: 1rem;
    padding: 0.85rem 1.2rem;
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: 10px;
    transition: border-color 0.2s, background 0.2s, transform 0.2s;
  }

  .team-row:hover {
    border-color: var(--purple-border-bright);
    background: var(--purple-pale2);
    transform: translateX(4px);
  }

  .team-emoji { font-size: 1rem; text-align: center; }
  .team-role  { font-size: 0.84rem; color: var(--text-muted); font-weight: 500; }
  .team-name  {
    font-family: var(--mono);
    font-size: 0.76rem;
    color: var(--purple);
    text-align: right;
    white-space: nowrap;
    font-weight: 700;
  }

  .footer {
    text-align: center;
    padding-top: 4rem;
    border-top: 1px solid var(--border);
    margin-top: 4rem;
  }

  .footer-logo { font-family: var(--mono); font-size: 1.5rem; font-weight: 700; margin-bottom: 0.5rem; }
  .footer-made { font-size: 0.82rem; color: var(--text-dim); }
  .footer-heart { color: var(--purple); }

  .animate-in {
    opacity: 0;
    transform: translateY(16px);
    transition: opacity 0.55s ease, transform 0.55s ease;
  }

  .animate-in.visible { opacity: 1; transform: translateY(0); }

  .progress-bar {
    position: fixed;
    top: 0; left: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--purple), var(--purple-light));
    z-index: 100;
    transition: width 0.1s;
    border-radius: 0 2px 2px 0;
  }
</style>
</head>
<body>

<div class="progress-bar" id="progress"></div>

<div class="wrapper">

  <header class="hero">
    <div class="hero-glow"></div>
    <div class="logo-line">
      <span class="logo-go">Go</span><span class="logo-shiet">Shiet</span>
    </div>
    <p class="hero-tagline">Система автоматического расписания</p>
    <p class="hero-desc">
      Мощное решение для автоматизации образовательного процесса — умный алгоритм генерации, удобный веб-интерфейс и мгновенные уведомления.
    </p>
    <div class="badges">
      <span class="badge">Python</span>
      <span class="badge">PostgreSQL</span>
      <span class="badge">Telegram Bot</span>
      <span class="badge">Web Interface</span>
    </div>
  </header>

  <div class="divider animate-in"></div>

  <section class="animate-in">
    <div class="section-label">// 01 — Access Model</div>
    <h2 class="section-title">Ролевая система</h2>
    <div class="roles-grid">
      <div class="role-card">
        <div class="role-icon">👑</div>
        <div class="role-title">Короли</div>
        <div class="role-desc">Глобальное управление: создание структуры университета и профилей преподавателей</div>
      </div>
      <div class="role-card">
        <div class="role-icon">🛡️</div>
        <div class="role-title">Администраторы</div>
        <div class="role-desc">Полный контроль над преподавательским составом, инфраструктурой, предметами и расписанием</div>
      </div>
      <div class="role-card">
        <div class="role-icon">🎓</div>
        <div class="role-title">Преподаватели</div>
        <div class="role-desc">Регистрация и гибкая настройка желаемого графика — пары подряд, пары в день, дни недели</div>
      </div>
      <div class="role-card">
        <div class="role-icon">👀</div>
        <div class="role-title">Студенты</div>
        <div class="role-desc">Гостевой доступ без регистрации — просмотр расписания прямо с сайта</div>
      </div>
    </div>
  </section>

  <div class="divider animate-in"></div>

  <section class="animate-in">
    <div class="section-label">// 02 — Core Modules</div>
    <h2 class="section-title">Функциональные модули</h2>
    <div class="modules-grid">
      <div class="module-card">
        <div class="module-number">MODULE_01</div>
        <div class="module-title">🌐 Веб-интерфейс</div>
        <ul class="module-features">
          <li>Фильтры по университету, направлению, курсу</li>
          <li>Точечные фильтры под студента, преподавателя, аудиторию</li>
          <li>Красивая недельная сетка расписания</li>
          <li>Машина времени — навигация по датам</li>
          <li>Дашборд с численной аналитикой</li>
        </ul>
      </div>
      <div class="module-card">
        <div class="module-number">MODULE_02</div>
        <div class="module-title">🤖 Telegram-бот</div>
        <ul class="module-features">
          <li>Push-уведомления о начале пар</li>
          <li>Оповещения о любых изменениях в расписании</li>
          <li>Рассылка важных новостей филиала</li>
          <li>Личный кабинет с настройкой подписок</li>
        </ul>
      </div>
      <div class="module-card">
        <div class="module-number">MODULE_03</div>
        <div class="module-title">⚙️ Алгоритм генерации</div>
        <ul class="module-features">
          <li>Математический расчёт сетки занятий</li>
          <li>Учёт всех ограничений преподавателей</li>
          <li>Учёт доступности аудиторий</li>
          <li>Возможность ручной корректировки</li>
        </ul>
      </div>
    </div>
  </section>

  <div class="divider animate-in"></div>

  <section class="animate-in">
    <div class="section-label">// 03 — Tech Stack</div>
    <h2 class="section-title">Технологии</h2>
    <div class="terminal">
      <div class="terminal-bar">
        <div class="dot dot-r"></div>
        <div class="dot dot-y"></div>
        <div class="dot dot-g"></div>
      </div>
      <div class="terminal-body">
        <span class="comment"># GoShiet v1.0 — system overview</span><br>
        <span class="cmd">$ python --version</span><br>
        <span class="out">→ Backend, Algorithm, Telegram Bot</span><br>
        <span class="cmd">$ psql --version</span><br>
        <span class="out">→ PostgreSQL — relational database</span><br>
        <span class="cmd">$ systemctl status goshiet</span><br>
        <span class="out">● goshiet.service — active (running) ✓</span>
      </div>
    </div>
    <div class="stack-row">
      <span class="stack-pill">Python</span>
      <span class="stack-pill">PostgreSQL</span>
      <span class="stack-pill">Telegram API</span>
      <span class="stack-pill">HTML / CSS / JS</span>
      <span class="stack-pill">Scheduling Algorithm</span>
    </div>
  </section>

  <div class="divider animate-in"></div>

  <section class="animate-in">
    <div class="section-label">// 04 — The Team</div>
    <h2 class="section-title">Команда проекта</h2>
    <div class="team-grid">
      <div class="team-row">
        <span class="team-emoji">🗄️</span>
        <span class="team-role">Проектирование и создание БД</span>
        <span class="team-name">Ризаев Амирхан</span>
      </div>
      <div class="team-row">
        <span class="team-emoji">⚙️</span>
        <span class="team-role">Backend сайта</span>
        <span class="team-name">Гайратов Амирхон</span>
      </div>
      <div class="team-row">
        <span class="team-emoji">🎨</span>
        <span class="team-role">Frontend сайта</span>
        <span class="team-name">Ибрахимова Севинч</span>
      </div>
      <div class="team-row">
        <span class="team-emoji">💬</span>
        <span class="team-role">Telegram-бот — дизайн и реализация</span>
        <span class="team-name">Сейдирахимов Нурзат</span>
      </div>
      <div class="team-row">
        <span class="team-emoji">🎛️</span>
        <span class="team-role">Админ-панели — ввод данных, интерфейс</span>
        <span class="team-name">Велиляев Алим</span>
      </div>
      <div class="team-row">
        <span class="team-emoji">🧠</span>
        <span class="team-role">Алгоритм составления расписания</span>
        <span class="team-name">Гольденгорин Виталий</span>
      </div>
    </div>
  </section>

  <footer class="footer animate-in">
    <div class="footer-logo">
      <span style="color:#1a1625;">Go</span><span style="color:var(--purple);">Shiet</span>
    </div>
    <p class="footer-made">Разработано с <span class="footer-heart">♥</span> командой GoShiet</p>
  </footer>

</div>

<script>
  const progress = document.getElementById('progress');
  window.addEventListener('scroll', () => {
    const h = document.documentElement;
    progress.style.width = (h.scrollTop / (h.scrollHeight - h.clientHeight) * 100) + '%';
  });

  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('.animate-in').forEach(el => observer.observe(el));
</script>
</body>
</html>
