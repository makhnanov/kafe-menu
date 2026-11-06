#!/usr/bin/env python3
"""Генератор PDF с треугольными вкладышами «на чай» — вторая боковина подставки.

Форма та же, что у make-profile.py (контур Profile.dxf): видно только
внутренний треугольник, губы и нижняя планка прячутся в рамке.

Содержимое: фото мангала фоном, Kaspi QR ромбом в верхней части, подпись
и стрелка вниз.

    ./make-tips.py
    ./make-tips.py --count 10
    ./make-tips.py --image img/tips-art.png --qr img/tips-qr.png

QR вырезан из каспи-скриншота: 45 модулей (версия 7), 425 x 425 px.
Размер на печати подбирается автоматически — максимальный, который влезает
в треугольник на своей высоте; скрипт печатает мм на модуль, чтобы было
видно, насколько уверенно он прочитается.

Нужен google-chrome (или chromium).
"""
import argparse, math, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent

# --- геометрия из Profile.dxf, мм (как в make-profile.py) ---
SHEET = [(0.0, 115.1803), (0.0, 93.8581), (34.1616, 0.0),
         (39.2638, 0.0), (73.4254, 93.8581), (73.4254, 115.1803)]
SHEET_W, SHEET_H = 73.4254, 115.1803
APEX = (36.7127, 3.2241)
BASE_Y = 95.1945
BASE_L, BASE_R = 3.2382, 70.1872
SLOPE = math.radians(20.0)
BLEED = 2.6

# --- раскладка содержимого по высоте листа, мм от верха ---
TEXT_BOTTOM = 93.5      # низ плашки, выше видимого основания на 1.7 мм
ARROW_H = 8.2           # стрелка — на своей плашке справа от подписи
ARROW_W = 5.6
ARROW_GAP = 2.0         # просвет между плашками
TEXT_SIZE = 3.0
TEXT_PAD = 1.4
QR_SIZE = 22.0          # сторона самого кода, мм — от неё считается высота
QR_GAP = 1.0            # минимальный просвет между ромбом и подписью
QR_MARGIN = 1.5         # запас от наклонных кромок окна
QR_QUIET = 3            # тихая зона вокруг кода, в модулях
QR_MODULES = 45
QR_BORDER = 0.35

TEXT_LINES = ["Чаевые — это не мелочь.", "Но мелочь тоже можно)"]

COLS, ROWS, GAP = 2, 2, 5.0


def tool(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    sys.exit(f"не найдено: {' / '.join(names)}")


def inset(poly, d):
    """Выпуклый контур, поджатый внутрь на d мм."""
    if d <= 0:
        return poly
    area = sum(poly[i][0]*poly[(i+1) % len(poly)][1] - poly[(i+1) % len(poly)][0]*poly[i][1]
               for i in range(len(poly)))
    s = -1.0 if area > 0 else 1.0
    lines = []
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i+1) % len(poly)]
        dx, dy = x2-x1, y2-y1
        L = math.hypot(dx, dy)
        lines.append((x1 + s*dy/L*d, y1 - s*dx/L*d, dx, dy))
    out = []
    for i in range(len(lines)):
        x1, y1, dx1, dy1 = lines[i-1]
        x2, y2, dx2, dy2 = lines[i]
        t = ((x2-x1)*dy2 - (y2-y1)*dx2) / (dx1*dy2 - dy1*dx2)
        out.append((round(x1 + dx1*t, 4), round(y1 + dy1*t, 4)))
    return out


def pts(poly):
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in poly)


def half_width(y):
    """Полуширина видимого треугольника на высоте y."""
    return max(0.0, (y - APEX[1]) * math.tan(SLOPE))


def view_triangle():
    return [(APEX[0], APEX[1] - BLEED/math.sin(SLOPE)),
            (BASE_R + BLEED/math.cos(SLOPE), BASE_Y + BLEED),
            (BASE_L - BLEED/math.cos(SLOPE), BASE_Y + BLEED)]


def layout(qr_size=QR_SIZE):
    """Ромб поднимаем настолько, насколько позволяет его же размер: в самой
    широкой точке он должен уложиться в окно с запасом QR_MARGIN."""
    text_h = max(len(TEXT_LINES) * TEXT_SIZE * 1.28, ARROW_H) + 2 * TEXT_PAD
    text_top = TEXT_BOTTOM - text_h

    # сторона плашки P = S + 2*(тихая зона) + 2*(рамка), половина диагонали r = P/sqrt(2)
    plate = qr_size * (1 + 2*QR_QUIET/QR_MODULES) + 2*QR_BORDER
    r = plate / math.sqrt(2)
    # самая широкая точка ромба — на высоте его центра: r <= tg*(yc - APEX_Y) - запас
    yc = APEX[1] + (r + QR_MARGIN) / math.tan(SLOPE)
    if yc + r > text_top - QR_GAP:
        sys.exit(f"QR {qr_size} мм не помещается над подписью: "
                 f"низ ромба {yc + r:.1f} мм, подпись начинается с {text_top:.1f} мм")
    return {"qr": qr_size, "qr_y": yc, "qr_r": r,
            "qr_top": yc - r, "qr_bottom": yc + r,
            "text_y": (text_top + TEXT_BOTTOM) / 2,
            "text_room": 2 * half_width(text_top),
            "middle": (APEX[1] + BASE_Y) / 2}


def arrow_svg():
    """Стрелка вниз на самой плашке — золото по кремовому, ореол не нужен."""
    w, h, cx = ARROW_W, ARROW_H, ARROW_W / 2
    shaft = f'M {cx:.2f},0.8 L {cx:.2f},{h-2.1:.2f}'
    head = f'M {cx-2.1:.2f},{h-3.4:.2f} L {cx:.2f},{h-0.7:.2f} L {cx+2.1:.2f},{h-3.4:.2f}'
    return (f'<svg class="arrow" viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm">'
            f'<path d="{shaft}" fill="none" stroke="#c8881c" stroke-width="1.0"'
            f' stroke-linecap="round"/>'
            f'<path d="{head}" fill="none" stroke="#c8881c" stroke-width="1.0"'
            f' stroke-linecap="round" stroke-linejoin="round"/></svg>')


def card(n, img, qr, L):
    cut = inset(SHEET, 0.2)
    lines = "<br>".join(TEXT_LINES)
    tri = view_triangle()
    x0, x1, y0, y1 = tri[2][0], tri[1][0], tri[0][1], tri[1][1]
    return f"""
    <div class="cell">
      <svg viewBox="0 0 {SHEET_W} {SHEET_H}" xmlns="http://www.w3.org/2000/svg">
        <defs><clipPath id="v{n}"><polygon points="{pts(tri)}"/></clipPath></defs>
        <polygon points="{pts(cut)}" fill="#fdfaf3"/>
        <g clip-path="url(#v{n})">
          <image href="{img}" x="{x0:.3f}" y="{y0:.3f}"
                 width="{x1-x0:.3f}" height="{y1-y0:.3f}"
                 preserveAspectRatio="xMidYMid slice"/>
        </g>
        <polygon points="{pts(cut)}" fill="none" stroke="#cfc8ba" stroke-width="0.17"
                 stroke-dasharray="1.2 1.1"/>
        <text x="{SHEET_W/2:.2f}" y="{SHEET_H-2.4:.2f}" text-anchor="middle"
              font-family="Helvetica,Arial,sans-serif" font-size="1.7"
              fill="#b9b1a1">{n} &#183; TIPS</text>
      </svg>
      <div class="qr" style="top:{L['qr_y']:.2f}mm"><img src="{qr}" alt=""></div>
      <div class="tiprow" style="top:{L['text_y']:.2f}mm">
        <div class="plate">{lines}</div>
        <div class="plate arrowbox">{arrow_svg()}</div>
      </div>
    </div>"""


def build_html(count, img, qr, L):
    per = COLS * ROWS
    pages = [list(range(i+1, min(i+per, count)+1)) for i in range(0, count, per)]
    sheet_w = COLS * SHEET_W + (COLS - 1) * GAP
    sheet_h = ROWS * SHEET_H + (ROWS - 1) * GAP
    mar_x, mar_y = (210 - sheet_w) / 2, (297 - sheet_h) / 2

    body = ""
    for page in pages:
        body += '<div class="sheet">' + "".join(card(n, img, qr, L) for n in page)
        body += '<div class="cell"></div>' * (per - len(page)) + "</div>\n"

    quiet = L["qr"] * QR_QUIET / QR_MODULES
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>Вкладыши «на чай»</title>
<style>
  @page {{ size: A4; margin: {mar_y:.3f}mm {mar_x:.3f}mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ background: #fff; }}
  .sheet {{
    width: {sheet_w:.3f}mm; height: {sheet_h:.3f}mm;
    display: grid;
    grid-template-columns: repeat({COLS}, {SHEET_W:.3f}mm);
    grid-template-rows: repeat({ROWS}, {SHEET_H:.3f}mm);
    gap: {GAP}mm;
    page-break-after: always;
  }}
  .sheet:last-child {{ page-break-after: auto; }}
  .cell {{ position: relative; width: {SHEET_W:.3f}mm; height: {SHEET_H:.3f}mm; }}
  .cell svg {{ position: absolute; left: 0; top: 0; }}
  .cell > svg {{ width: {SHEET_W:.3f}mm; height: {SHEET_H:.3f}mm; }}

  /* Kaspi QR ромбом: крутим всю плашку, код остаётся ровным внутри неё */
  .qr {{
    position: absolute; left: 50%;
    transform: translate(-50%, -50%) rotate(45deg);
    background: #fff; padding: {quiet:.2f}mm;
    border: {QR_BORDER}mm solid #c8881c; border-radius: 1.6mm;
    box-shadow: 0 0 2mm rgba(0,0,0,.18);
  }}
  .qr img {{ display: block; width: {L['qr']:.2f}mm; height: {L['qr']:.2f}mm; }}

  .tiprow {{
    position: absolute; left: 50%; transform: translate(-50%, -50%);
    display: flex; align-items: stretch; gap: {ARROW_GAP}mm;
  }}
  .plate {{
    padding: {TEXT_PAD}mm 3.4mm; white-space: nowrap; text-align: center;
    background: rgba(253,250,243,.94);
    border: 0.32mm solid #c7ab6a; border-radius: 2.4mm;
    font-family: Georgia, "Times New Roman", serif;
    font-size: {TEXT_SIZE}mm; line-height: 1.28; color: #6b4a12;
  }}
  .plate.arrowbox {{
    display: flex; align-items: center; justify-content: center;
    padding: {TEXT_PAD}mm 1.6mm; line-height: 0;
  }}
  .plate svg.arrow {{ position: static; flex: 0 0 auto; }}
</style>
</head>
<body>
{body}</body>
</html>""", count, len(pages)


def main():
    ap = argparse.ArgumentParser(description="PDF с треугольными вкладышами «на чай»")
    ap.add_argument("--count", type=int, default=7, help="сколько вкладышей (по умолчанию 7)")
    ap.add_argument("--image", default="img/tips-art.jpg", help="фоновое фото")
    ap.add_argument("--qr", default="img/tips-qr.png", help="вырезанный QR")
    ap.add_argument("--qr-size", type=float, default=QR_SIZE,
                    help=f"сторона кода, мм (по умолчанию {QR_SIZE}); "
                         "чем меньше, тем выше он встаёт")
    ap.add_argument("-o", "--out", default=str(HERE / "tips-cards.pdf"))
    a = ap.parse_args()

    paths = []
    for f in (a.image, a.qr):
        p = pathlib.Path(f).resolve()
        if not p.exists():
            sys.exit(f"нет файла: {p}")
        paths.append(p.as_uri())

    L = layout(a.qr_size)
    out = pathlib.Path(a.out).resolve()
    html, n_items, n_pages = build_html(a.count, paths[0], paths[1], L)

    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "tips.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [tool("google-chrome", "chromium", "chromium-browser"),
             "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--print-to-pdf={out}", page.as_uri()],
            check=True, capture_output=True,
        )

    print(f"вкладышей: {n_items}, листов A4: {n_pages} -> {out}")
    print(f"QR: {L['qr']:.1f} x {L['qr']:.1f} мм, {L['qr']/QR_MODULES:.3f} мм на модуль, "
          f"ромб {2*L['qr_r']:.1f} мм по диагонали")
    print(f"ромб: центр на {L['qr_y']:.1f} мм от верха (середина окна — {L['middle']:.1f}), "
          f"верхний угол {L['qr_top']:.1f}, нижний {L['qr_bottom']:.1f}, "
          f"до наклонных кромок {QR_MARGIN} мм")
    print(f"подпись со стрелкой: центр на {L['text_y']:.1f} мм, "
          f"окно по верху плашки {L['text_room']:.1f} мм")
    print("печатать в масштабе 100%; один экземпляр проверить сканером до всего тиража")


if __name__ == "__main__":
    main()
