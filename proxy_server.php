<?php
/**
 * IPv6 ПРОКСИ СЕРВЕР - АВТОНОМНЫЙ ЗАПУСК
 * Просто запусти: php proxy_final.php
 * Веб-интерфейс: http://31.162.195.216:8888
 */

// ТВОИ ДАННЫЕ
define('PUBLIC_IPV4', '31.162.195.216');
define('PUBLIC_IPV6', '2a01:540:4362:d200:a7e:d0e4:f17c:8dc5');
define('SUBNET', '2a01:540:4362:d200::/64');
define('WEB_PORT', 8888);
define('PROXY_START_PORT', 10000);

// Файлы данных
define('DATA_FILE', __DIR__ . '/proxy_data.json');
define('LOG_FILE', __DIR__ . '/proxy_log.txt');

// Загрузка БД
function loadDB() {
    if (file_exists(DATA_FILE)) {
        return json_decode(file_get_contents(DATA_FILE), true);
    }
    return [
        'proxies' => [],
        'settings' => ['start_port' => PROXY_START_PORT, 'interface' => 'wlan0', 'auto_activate' => false],
        'stats' => ['total_generated' => 0, 'active' => 0, 'total_requests' => 0]
    ];
}

function saveDB($db) {
    file_put_contents(DATA_FILE, json_encode($db, JSON_PRETTY_PRINT));
}

function logMsg($msg) {
    file_put_contents(LOG_FILE, "[" . date('Y-m-d H:i:s') . "] $msg\n", FILE_APPEND);
}

// Генерация прокси
function genProxies(&$db, $count, $port) {
    $parts = explode('/', SUBNET);
    $prefix = $parts[0];
    $prefixParts = explode(':', rtrim($prefix, ':'));
    while (count($prefixParts) < 4) $prefixParts[] = '0';
    $basePrefix = implode(':', array_slice($prefixParts, 0, 4));
    
    $existing = array_column($db['proxies'], 'address');
    $generated = [];
    
    for ($i = 0; $i < $count; $i++) {
        do {
            $blocks = [];
            for ($b = 0; $b < 4; $b++) {
                $blocks[] = dechex(mt_rand(0, 65535));
            }
            $address = "$basePrefix:" . implode(':', $blocks);
        } while (in_array($address, $existing));
        
        $existing[] = $address;
        
        $proxy = [
            'id' => bin2hex(random_bytes(8)),
            'address' => $address,
            'port' => $port,
            'active' => false,
            'created' => date('Y-m-d H:i:s'),
            'requests' => 0
        ];
        
        $db['proxies'][] = $proxy;
        $generated[] = $proxy;
        
        if ($db['settings']['auto_activate']) {
            exec("ip -6 addr add $address/64 dev {$db['settings']['interface']} 2>&1", $out, $ret);
            if ($ret === 0 || strpos(implode(' ', $out), 'exist') !== false) {
                $proxy['active'] = true;
            }
        }
    }
    
    $db['stats']['total_generated'] = count($db['proxies']);
    $db['stats']['active'] = count(array_filter($db['proxies'], fn($p) => $p['active']));
    saveDB($db);
    logMsg("Сгенерировано $count прокси");
    return $generated;
}

// Запуск веб-сервера (если скрипт запущен без аргументов)
if (php_sapi_name() === 'cli' && !isset($argv[1])) {
    echo "╔══════════════════════════════════════════════════════════════╗\n";
    echo "║         IPv6 ПРОКСИ СЕРВЕР - ЗАПУСК ВЕБ-ИНТЕРФЕЙСА         ║\n";
    echo "╠══════════════════════════════════════════════════════════════╣\n";
    echo "║ Веб-интерфейс: http://" . PUBLIC_IPV4 . ":" . WEB_PORT . str_repeat(" ", 26 - strlen(PUBLIC_IPV4 . ":" . WEB_PORT)) . "║\n";
    echo "║ Локальный:     http://localhost:" . WEB_PORT . "                         ║\n";
    echo "║ Прокси порт:   " . PROXY_START_PORT . "                                       ║\n";
    echo "║ Для остановки: Ctrl+C                                       ║\n";
    echo "╚══════════════════════════════════════════════════════════════╝\n";
    
    // Запускаем встроенный PHP сервер
    $cmd = sprintf(
        'php -S %s:%d %s',
        '0.0.0.0',
        WEB_PORT,
        __FILE__
    );
    
    echo "Запуск сервера...\n";
    passthru($cmd);
    exit;
}

// ===== ВЕБ-ЧАСТЬ =====
$db = loadDB();

// Проверяем, что мы в веб-режиме
if (!isset($_SERVER['REQUEST_METHOD'])) {
    // Это CLI режим (например, php -S)
    return false;
}

$request = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
$method = $_SERVER['REQUEST_METHOD'];

// API маршруты
if (preg_match('#^/api/#', $request)) {
    header('Content-Type: application/json');
    
    if ($request === '/api/generate' && $method === 'POST') {
        $count = min(500, max(1, (int)($_POST['count'] ?? 10)));
        $port = (int)($_POST['port'] ?? PROXY_START_PORT);
        $proxies = genProxies($db, $count, $port);
        echo json_encode(['success' => true, 'count' => count($proxies)]);
        exit;
    }
    
    if ($request === '/api/activate' && $method === 'POST') {
        $ids = json_decode($_POST['ids'] ?? '[]', true);
        $count = 0;
        foreach ($db['proxies'] as &$p) {
            if (in_array($p['id'], $ids) && !$p['active']) {
                exec("ip -6 addr add {$p['address']}/64 dev {$db['settings']['interface']} 2>&1", $out, $ret);
                if ($ret === 0 || strpos(implode(' ', $out), 'exist') !== false) {
                    $p['active'] = true;
                    $count++;
                }
            }
        }
        $db['stats']['active'] = count(array_filter($db['proxies'], fn($p) => $p['active']));
        saveDB($db);
        echo json_encode(['success' => true, 'count' => $count]);
        exit;
    }
    
    if ($request === '/api/deactivate' && $method === 'POST') {
        $ids = json_decode($_POST['ids'] ?? '[]', true);
        $count = 0;
        foreach ($db['proxies'] as &$p) {
            if (in_array($p['id'], $ids) && $p['active']) {
                exec("ip -6 addr del {$p['address']}/64 dev {$db['settings']['interface']} 2>&1");
                $p['active'] = false;
                $count++;
            }
        }
        $db['stats']['active'] = count(array_filter($db['proxies'], fn($p) => $p['active']));
        saveDB($db);
        echo json_encode(['success' => true, 'count' => $count]);
        exit;
    }
    
    if ($request === '/api/delete' && $method === 'POST') {
        $ids = json_decode($_POST['ids'] ?? '[]', true);
        foreach ($db['proxies'] as $p) {
            if (in_array($p['id'], $ids) && $p['active']) {
                exec("ip -6 addr del {$p['address']}/64 dev {$db['settings']['interface']} 2>&1");
            }
        }
        $db['proxies'] = array_values(array_filter($db['proxies'], fn($p) => !in_array($p['id'], $ids)));
        $db['stats']['total_generated'] = count($db['proxies']);
        $db['stats']['active'] = count(array_filter($db['proxies'], fn($p) => $p['active']));
        saveDB($db);
        echo json_encode(['success' => true, 'count' => count($ids)]);
        exit;
    }
    
    if ($request === '/api/status') {
        echo json_encode([
            'ipv4' => PUBLIC_IPV4,
            'ipv6' => PUBLIC_IPV6,
            'total' => count($db['proxies']),
            'active' => $db['stats']['active']
        ]);
        exit;
    }
    
    if ($request === '/api/list') {
        echo json_encode($db['proxies']);
        exit;
    }
    
    if ($request === '/api/export') {
        header('Content-Type: text/plain');
        foreach ($db['proxies'] as $p) {
            if ($p['active']) echo "{$p['address']}:{$p['port']}\n";
        }
        exit;
    }
}

// Отрисовка HTML
function getLogs($n = 50) {
    if (!file_exists(LOG_FILE)) return [];
    return array_slice(array_reverse(file(LOG_FILE) ?: []), 0, $n);
}
?>
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPv6 Прокси Сервер | <?= PUBLIC_IPV4 ?></title>
    <style>
        :root{--bg:#0a0e17;--card:#111827;--border:#1e293b;--accent:#6366f1;--green:#10b981;--red:#ef4444;--text:#e2e8f0;--text2:#94a3b8}
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:system-ui;background:var(--bg);color:var(--text);line-height:1.6}
        .header{background:linear-gradient(135deg,#1e1b4b,#0f172a);border-bottom:2px solid var(--accent);padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem;position:sticky;top:0;z-index:100}
        .header h1{font-size:1.5rem;background:linear-gradient(135deg,var(--accent),#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:800}
        .badge{padding:.25rem .75rem;border-radius:9999px;font-weight:600;font-size:.75rem;text-transform:uppercase}
        .badge-s{background:rgba(16,185,129,0.2);color:var(--green);border:1px solid rgba(16,185,129,0.3)}
        .ip{font-family:monospace;background:rgba(0,0,0,0.3);padding:.25rem .5rem;border-radius:.375rem;border:1px solid var(--border);font-size:.85rem}
        nav{background:var(--card);border-bottom:1px solid var(--border);padding:.5rem 2rem;display:flex;gap:.5rem;flex-wrap:wrap}
        nav a{color:var(--text2);text-decoration:none;padding:.5rem 1rem;border-radius:.5rem;font-size:.875rem;cursor:pointer;transition:all .2s}
        nav a:hover,nav a.active{background:var(--accent);color:#fff}
        .container{max-width:1400px;margin:0 auto;padding:2rem}
        .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;margin-bottom:2rem}
        .card{background:var(--card);padding:1.5rem;border-radius:.75rem;border:1px solid var(--border);transition:.3s}
        .card:hover{border-color:var(--accent);transform:translateY(-2px)}
        .card .lbl{font-size:.75rem;text-transform:uppercase;color:var(--text2);margin-bottom:.5rem}
        .card .val{font-size:2rem;font-weight:800;background:linear-gradient(135deg,var(--accent),#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
        .panel{background:var(--card);border-radius:.75rem;border:1px solid var(--border);padding:1.5rem;margin-bottom:1.5rem}
        .btn{padding:.5rem 1rem;border:none;border-radius:.5rem;cursor:pointer;font-weight:600;font-size:.875rem;transition:.2s;display:inline-flex;align-items:center;gap:.5rem;text-decoration:none}
        .btn-p{background:var(--accent);color:#fff}
        .btn-p:hover{background:#818cf8;transform:translateY(-1px)}
        .btn-s{background:var(--green);color:#fff}
        .btn-d{background:var(--red);color:#fff}
        .btn-sm{padding:.25rem .75rem;font-size:.8rem}
        .btn-g{display:flex;gap:.5rem;flex-wrap:wrap}
        input[type=number]{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:.5rem .75rem;border-radius:.5rem;font-size:.875rem}
        input:focus{outline:none;border-color:var(--accent)}
        table{width:100%;border-collapse:collapse}
        th{background:rgba(0,0,0,0.3);padding:.75rem;text-align:left;font-size:.75rem;text-transform:uppercase;color:var(--text2);border-bottom:2px solid var(--border)}
        td{padding:.75rem;border-bottom:1px solid var(--border);font-size:.875rem}
        tr:hover{background:rgba(99,102,241,0.05)}
        .addr{font-family:monospace;font-size:.8rem;color:#818cf8}
        .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:.5rem}
        .dot-on{background:var(--green);box-shadow:0 0 10px rgba(16,185,129,0.5)}
        .dot-off{background:var(--text2)}
        .log-c{max-height:500px;overflow-y:auto;font-family:monospace;font-size:.8rem}
        .log-l{padding:.5rem;border-bottom:1px solid var(--border);color:var(--text2)}
        .toast{position:fixed;top:1rem;right:1rem;z-index:1000}
        .toast-m{padding:1rem 1.5rem;border-radius:.5rem;color:#fff;font-weight:500;margin-bottom:.5rem;animation:slideIn .3s}
        .toast-s{background:var(--green)}
        .toast-e{background:var(--red)}
        @keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
    </style>
</head>
<body>
<div class="header">
    <h1>🌐 IPv6 Прокси Сервер</h1>
    <div>
        <span class="ip"><?= PUBLIC_IPV4 ?></span>
        <span class="badge badge-s">● <?= $db['stats']['active'] ?> активных</span>
    </div>
</div>

<nav>
    <a href="#" class="active" onclick="showTab('dashboard');return false">📊 Дашборд</a>
    <a href="#" onclick="showTab('proxies');return false">📋 Прокси</a>
    <a href="#" onclick="showTab('generate');return false">🚀 Генерация</a>
    <a href="#" onclick="showTab('logs');return false">📝 Логи</a>
</nav>

<div class="container">
    <div id="toast-container" class="toast"></div>

    <div id="tab-dashboard">
        <div class="grid">
            <div class="card"><div class="lbl">Всего</div><div class="val"><?= number_format($db['stats']['total_generated']) ?></div></div>
            <div class="card"><div class="lbl">Активных</div><div class="val"><?= number_format($db['stats']['active']) ?></div></div>
            <div class="card"><div class="lbl">Подсеть</div><div class="val" style="font-size:1.5rem">/64</div><div style="font-size:.8rem;color:var(--text2)"><?= SUBNET ?></div></div>
            <div class="card"><div class="lbl">Порт</div><div class="val"><?= PROXY_START_PORT ?></div></div>
        </div>

        <div class="panel">
            <h3>⚡ Действия</h3>
            <div class="btn-g">
                <button class="btn btn-p" onclick="genProxies()">🚀 +10 прокси</button>
                <button class="btn btn-s" onclick="activateAll()">🟢 Активировать все</button>
                <button class="btn btn-d" onclick="deactivateAll()">🔴 Выключить все</button>
                <a href="/api/export" class="btn" style="background:var(--border);color:var(--text)">📥 Экспорт</a>
            </div>
        </div>
    </div>

    <div id="tab-proxies" style="display:none">
        <div class="panel">
            <div style="display:flex;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:1rem">
                <h3>📋 Список (<?= count($db['proxies']) ?>)</h3>
                <div class="btn-g">
                    <button class="btn btn-s btn-sm" onclick="bulk('activate')">🟢 Активировать</button>
                    <button class="btn btn-d btn-sm" onclick="bulk('deactivate')">🔴 Выключить</button>
                    <button class="btn btn-sm" style="background:var(--border);color:var(--text)" onclick="bulk('delete')">🗑 Удалить</button>
                </div>
            </div>
            <div style="overflow-x:auto">
                <table>
                    <thead><tr><th><input type="checkbox" onclick="document.querySelectorAll('.pcb').forEach(c=>c.checked=this.checked)"></th><th>IPv6</th><th>Порт</th><th>Статус</th><th>Создан</th><th></th></tr></thead>
                    <tbody>
                        <?php foreach ($db['proxies'] as $p): ?>
                        <tr>
                            <td><input type="checkbox" class="pcb" value="<?= $p['id'] ?>"></td>
                            <td><span class="addr"><?= htmlspecialchars($p['address']) ?></span></td>
                            <td><?= $p['port'] ?></td>
                            <td><span class="dot <?= $p['active'] ? 'dot-on' : 'dot-off' ?>"></span><?= $p['active'] ? 'Активен' : 'Выкл' ?></td>
                            <td style="font-size:.8rem"><?= $p['created'] ?></td>
                            <td><button class="btn <?= $p['active'] ? 'btn-d' : 'btn-s' ?> btn-sm" onclick="toggleOne('<?= $p['id'] ?>',<?= $p['active'] ? 'false' : 'true' ?>)"><?= $p['active'] ? 'Выкл' : 'Вкл' ?></button></td>
                        </tr>
                        <?php endforeach ?>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <div id="tab-generate" style="display:none">
        <div class="panel">
            <h3>🚀 Генерация</h3>
            <div style="display:flex;gap:1rem;align-items:end;flex-wrap:wrap">
                <label>Кол-во: <input type="number" id="gcnt" value="10" min="1" max="500" style="width:100px"></label>
                <label>Порт: <input type="number" id="gport" value="<?= PROXY_START_PORT ?>" style="width:100px"></label>
                <button class="btn btn-p" onclick="genCustom()">⚡ Создать</button>
            </div>
            <div style="margin-top:1rem;padding:1rem;background:rgba(99,102,241,0.1);border-radius:.5rem">
                <strong>💡 Доступно 18.4 квинтиллиона адресов из <?= SUBNET ?></strong>
            </div>
        </div>
    </div>

    <div id="tab-logs" style="display:none">
        <div class="panel">
            <h3>📝 Логи</h3>
            <div class="log-c">
                <?php foreach (getLogs() as $l): ?><div class="log-l"><?= htmlspecialchars($l) ?></div><?php endforeach ?>
            </div>
        </div>
    </div>
</div>

<script>
function showTab(t){document.querySelectorAll('[id^="tab-"]').forEach(e=>e.style.display='none');document.getElementById('tab-'+t).style.display='block';document.querySelectorAll('nav a').forEach((a,i)=>{a.classList.toggle('active',a.textContent.toLowerCase().includes(t))})}

function toast(m,t){const c=document.getElementById('toast-container');const d=document.createElement('div');d.className='toast-m toast-'+(t==='success'?'s':'e');d.textContent=m;c.appendChild(d);setTimeout(()=>d.remove(),3000)}

async function api(url,body){
    const f=new FormData();
    for(const[k,v]of Object.entries(body))f.append(k,v);
    const r=await fetch(url,{method:'POST',body:f});
    return r.json()
}

async function genProxies(){
    const d=await api('/api/generate',{count:10,port:<?=PROXY_START_PORT?>});
    toast('✅ Создано '+d.count,'success');
    setTimeout(()=>location.reload(),1000)
}

async function genCustom(){
    const c=document.getElementById('gcnt').value;
    const p=document.getElementById('gport').value;
    const d=await api('/api/generate',{count:c,port:p});
    toast('✅ Создано '+d.count,'success');
    setTimeout(()=>location.reload(),1000)
}

async function toggleOne(id,act){
    const d=await api(act?'/api/activate':'/api/deactivate',{ids:JSON.stringify([id])});
    toast('✅ '+(act?'Активирован':'Деактивирован'),'success');
    setTimeout(()=>location.reload(),1000)
}

async function bulk(action){
    const ids=Array.from(document.querySelectorAll('.pcb:checked')).map(c=>c.value);
    if(!ids.length){toast('⚠️ Выберите прокси','error');return}
    if(action==='delete'&&!confirm('Удалить '+ids.length+'?'))return;
    const d=await api('/api/'+action,{ids:JSON.stringify(ids)});
    toast('✅ '+(action==='delete'?'Удалено':'Обработано')+' '+d.count,'success');
    setTimeout(()=>location.reload(),1000)
}

async function activateAll(){
    if(!confirm('Активировать ВСЕ?'))return;
    const r=await fetch('/api/list');const p=await r.json();
    const ids=p.filter(x=>!x.active).map(x=>x.id);
    if(!ids.length){toast('Все уже активны','success');return}
    const d=await api('/api/activate',{ids:JSON.stringify(ids)});
    toast('✅ '+d.count,'success');
    setTimeout(()=>location.reload(),1000)
}

async function deactivateAll(){
    if(!confirm('Выключить ВСЕ?'))return;
    const r=await fetch('/api/list');const p=await r.json();
    const ids=p.filter(x=>x.active).map(x=>x.id);
    if(!ids.length){toast('Все уже выключены','success');return}
    const d=await api('/api/deactivate',{ids:JSON.stringify(ids)});
    toast('✅ '+d.count,'success');
    setTimeout(()=>location.reload(),1000)
}
</script>
</body>
</html>
