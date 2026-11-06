#!/usr/bin/env python3
"""Генератор PDF с треугольными вкладышами в боковины подставки (Profile.dxf).

Схема та же, что у Front: видно только внутренний треугольник, всё вокруг
него — губы и нижняя планка — прячется внутри рамки. Там ничего полезного
не печатается, но бумага есть: лист должен держаться и опираться на планку.

    ./make-profile.py                      # 7 вкладышей, рисунок нарисован кодом
    ./make-profile.py --image art.png      # своя картинка вместо него
    ./make-profile.py --text-y 70          # поднять надпись (по умолчанию 92.2)
    ./make-profile.py --langs ru           # «Приятного аппетита!»

Картинка обрезается по видимому треугольнику с припуском, масштаб — по
большей стороне, центр по центру. Под неё нужен вертикальный кадр 2:3.

Нужен google-chrome (или chromium).
"""
import argparse, math, pathlib, shutil, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent

# --- геометрия из Profile.dxf, мм (начало координат — левый нижний угол листа,
#     ось Y вниз; числа получены переносом контура детали в эту систему) ---
SHEET = [(0.0, 115.1803), (0.0, 93.8581), (34.1616, 0.0),
         (39.2638, 0.0), (73.4254, 93.8581), (73.4254, 115.1803)]
SHEET_W, SHEET_H = 73.4254, 115.1803
APEX  = (36.7127, 3.2241)          # вершина окна
BASE_Y = 95.1945                   # основание окна
BASE_L, BASE_R = 3.2382, 70.1872   # углы основания окна
LIP = 3.5                          # губа вдоль наклонных кромок
SLOPE = math.radians(20.0)         # наклон кромки от вертикали
HIDDEN_B = SHEET_H - BASE_Y        # 19.986 — скрытый низ под планкой
BLEED = 2.6                        # на сколько рисунок заходит под губу

# --- раскладка на A4 (210 x 297 мм) ---
COLS, ROWS, GAP = 2, 2, 5.0

TEXTS = {"kk": ("Ас болсын!", 6.6), "ru": ("Приятного аппетита!", 4.7)}


def tool(*names):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    sys.exit(f"не найдено: {' / '.join(names)}")


def inset(poly, d):
    """Выпуклый контур, поджатый внутрь на d мм (зазор на вход в рамку)."""
    if d <= 0:
        return poly
    # ориентация: при обходе по списку площадь со знаком задаёт направление нормали
    area = sum(poly[i][0]*poly[(i+1) % len(poly)][1] - poly[(i+1) % len(poly)][0]*poly[i][1]
               for i in range(len(poly)))
    s = -1.0 if area > 0 else 1.0
    lines = []
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i+1) % len(poly)]
        dx, dy = x2-x1, y2-y1
        L = math.hypot(dx, dy)
        nx, ny = s*dy/L, -s*dx/L           # нормаль внутрь
        lines.append((x1 + nx*d, y1 + ny*d, dx, dy))
    out = []
    for i in range(len(lines)):
        x1, y1, dx1, dy1 = lines[i-1]
        x2, y2, dx2, dy2 = lines[i]
        den = dx1*dy2 - dy1*dx2
        t = ((x2-x1)*dy2 - (y2-y1)*dx2) / den
        out.append((round(x1 + dx1*t, 4), round(y1 + dy1*t, 4)))
    return out


def pts(poly):
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in poly)


def half_width(y):
    """Полуширина видимого треугольника на высоте y."""
    return max(0.0, (y - APEX[1]) * math.tan(SLOPE))


def pine(x, base, h):
    w = h * 0.42
    return (f'<rect x="{x-h*0.055:.2f}" y="{base-h*0.22:.2f}" width="{h*0.11:.2f}"'
            f' height="{h*0.25:.2f}" fill="#6d4a2b"/>'
            f'<polygon points="{x:.2f},{base-h:.2f} {x+w:.2f},{base-h*0.42:.2f}'
            f' {x-w:.2f},{base-h*0.42:.2f}" fill="#3f7d4c"/>'
            f'<polygon points="{x:.2f},{base-h*0.72:.2f} {x+w*1.12:.2f},{base-h*0.18:.2f}'
            f' {x-w*1.12:.2f},{base-h*0.18:.2f}" fill="#4a8c54"/>')


def view_triangle():
    """Видимый треугольник с припуском под губу."""
    bl = (BASE_L - BLEED/math.cos(SLOPE), BASE_Y + BLEED)
    br = (BASE_R + BLEED/math.cos(SLOPE), BASE_Y + BLEED)
    ap = (APEX[0], APEX[1] - BLEED/math.sin(SLOPE))
    return [ap, br, bl]


def banner(lang, text_y):
    """Плашка с пожеланием поверх картинки. Ширину задаёт сам текст плюс поля."""
    phrase, _ = TEXTS[lang]
    return f'<div class="banner {lang}" style="top:{text_y}mm">{phrase}</div>'


def picture(src):
    """Готовая картинка, вписанная в треугольник с припуском (кадрируется по центру)."""
    tri = view_triangle()
    x0, x1 = tri[2][0], tri[1][0]
    y0, y1 = tri[0][1], tri[1][1]
    return (f'<image href="{src}" x="{x0:.3f}" y="{y0:.3f}"'
            f' width="{x1-x0:.3f}" height="{y1-y0:.3f}"'
            f' preserveAspectRatio="xMidYMid slice"/>')


def scene(lang):
    """Запасной рисунок кодом, если своей картинки нет."""
    phrase, size = TEXTS[lang]
    view = view_triangle()
    s = []
    s.append('<defs>')
    s.append('<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
             '<stop offset="0" stop-color="#bcdcf0"/>'
             '<stop offset="0.55" stop-color="#dcecf5"/>'
             '<stop offset="1" stop-color="#ffe6bb"/></linearGradient>')
    s.append('<pattern id="check" width="5" height="5" patternUnits="userSpaceOnUse">'
             '<rect width="5" height="5" fill="#faf0dc"/>'
             '<rect width="2.5" height="2.5" fill="#e0655c"/>'
             '<rect x="2.5" y="2.5" width="2.5" height="2.5" fill="#e0655c"/></pattern>')
    s.append(f'<clipPath id="view"><polygon points="{pts(view)}"/></clipPath>')
    s.append('</defs>')

    g = []
    # небо и солнце
    g.append(f'<rect x="-4" y="-12" width="{SHEET_W+8:.2f}" height="{BASE_Y+8:.2f}" fill="url(#sky)"/>')
    g.append('<circle cx="36.7" cy="25" r="8.4" fill="#f6bf4e" opacity="0.22"/>')
    g.append('<circle cx="36.7" cy="25" r="5.1" fill="#f6bf4e"/>')
    for bx, by, bs in ((27.5, 41, 1.7), (45.5, 37.5, 1.3), (31, 46.5, 1.1)):
        g.append(f'<path d="M {bx-bs:.1f},{by:.1f} q {bs:.1f},-{bs*0.8:.1f} {bs:.1f},0'
                 f' q 0,-{bs*0.8:.1f} {bs:.1f},0" fill="none" stroke="#8aa7bb"'
                 f' stroke-width="0.32" stroke-linecap="round"/>')
    # дальняя гряда
    g.append('<polygon points="0,78 14,55 23,66 33,45.5 44,63 53,53 68,78"'
             ' fill="#9fb6c9"/>')
    # ближняя гряда со снегом
    g.append('<polygon points="-4,82 11,61 20,71 30,53 39,67 49,57.5 62,74 78,82"'
             ' fill="#7a95ab"/>')
    g.append('<path d="M 30,53 L 34.4,59.6 32.4,58.4 30.6,59.9 28.9,58.3 27.2,59.7 25.6,59.6 Z"'
             ' fill="#fbfdff"/>')
    g.append('<path d="M 49,57.5 L 52.6,62.8 51,61.9 49.5,63 48,61.7 46.4,62.9 45.4,62.8 Z"'
             ' fill="#fbfdff"/>')
    # холмы
    g.append('<path d="M -4,84 Q 11,72.5 25,80.5 Q 37,73.5 49,81 Q 62,75.5 78,84.5'
             ' L 78,102 L -4,102 Z" fill="#86bd6a"/>')
    for x, b, h in ((15.5, 81.5, 7.2), (21, 80.2, 5.4), (55, 81.5, 6.6), (60.5, 83, 5.0)):
        g.append(pine(x, b, h))
    # поляна
    g.append('<path d="M -4,88.5 Q 18,83.5 37,87 Q 56,90.5 78,85 L 78,102 L -4,102 Z"'
             ' fill="#9ad177"/>')

    # --- пикник ---
    # плед
    g.append('<polygon points="21.5,87.4 51.5,87.4 47.4,78.3 25.6,78.3" fill="url(#check)"/>')
    g.append('<polygon points="21.5,87.4 51.5,87.4 47.4,78.3 25.6,78.3" fill="none"'
             ' stroke="#c4554d" stroke-width="0.3"/>')
    # корзина с хлебом
    g.append('<path d="M 27.2,79.2 L 33.6,79.2 L 32.7,84.1 L 28.1,84.1 Z" fill="#c58f44"/>')
    g.append('<path d="M 27.6,80.8 L 33.2,80.8 M 27.9,82.4 L 32.9,82.4"'
             ' stroke="#a8742f" stroke-width="0.3"/>')
    g.append('<path d="M 27.9,79.2 Q 30.4,75.9 32.9,79.2" fill="none" stroke="#a8742f"'
             ' stroke-width="0.45"/>')
    g.append('<rect x="26.4" y="77.9" width="7.8" height="1.6" rx="0.8" fill="#d9a441"/>')
    g.append('<path d="M 28.1,78.3 L 28.7,79.1 M 30.3,78.3 L 30.9,79.1 M 32.5,78.3 L 33.1,79.1"'
             ' stroke="#b9822c" stroke-width="0.22"/>')
    # мангал с шашлыком
    g.append('<rect x="38.6" y="81.2" width="11.4" height="3.9" rx="0.5" fill="#4b423a"/>')
    g.append('<path d="M 39.4,85.1 L 38.3,87.2 M 49.2,85.1 L 50.3,87.2" stroke="#4b423a"'
             ' stroke-width="0.55" stroke-linecap="round"/>')
    g.append('<rect x="39.4" y="81.6" width="9.8" height="1.5" rx="0.5" fill="#ff7a2f"/>')
    for i, sy in enumerate((79.6, 80.4)):
        g.append(f'<line x1="37.9" y1="{sy:.1f}" x2="50.7" y2="{sy:.1f}" stroke="#b9b4ab"'
                 f' stroke-width="0.32"/>')
        for j in range(3):
            x = 40.2 + j*3.1 + i*0.5
            g.append(f'<rect x="{x:.1f}" y="{sy-0.95:.1f}" width="2.3" height="1.9" rx="0.75"'
                     f' fill="#8c4b2a"/>')
    for cx, cy, r in ((41.8, 77.2, 1.05), (43.9, 75.3, 1.35), (46.2, 73.3, 1.0)):
        g.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" opacity="0.38"/>')

    s.append(f'<g clip-path="url(#view)">{"".join(g)}</g>')
    return "".join(s)


def card(lang, n, clearance, img, text_y):
    cut = inset(SHEET, clearance / 2)
    art = (f'<defs><clipPath id="view"><polygon points="{pts(view_triangle())}"/></clipPath>'
           f'</defs><g clip-path="url(#view)">{picture(img)}</g>') if img else scene(lang)
    return f"""
    <div class="cell">
      <svg viewBox="0 0 {SHEET_W} {SHEET_H}" xmlns="http://www.w3.org/2000/svg">
        <polygon points="{pts(cut)}" fill="#fdfaf3"/>
        {art}
        <polygon points="{pts(cut)}" fill="none" stroke="#cfc8ba" stroke-width="0.17"
                 stroke-dasharray="1.2 1.1"/>
        <text x="{SHEET_W/2:.2f}" y="{SHEET_H-2.4:.2f}" text-anchor="middle"
              font-family="Helvetica,Arial,sans-serif" font-size="1.7"
              fill="#b9b1a1">{n} &#183; {lang.upper()}</text>
      </svg>
      {banner(lang, text_y)}
    </div>"""


def build_html(count, langs, clearance, img, text_y):
    items = [(i + 1, langs[i % len(langs)]) for i in range(count)]
    per = COLS * ROWS
    pages = [items[i:i + per] for i in range(0, len(items), per)]

    sheet_w = COLS * SHEET_W + (COLS - 1) * GAP
    sheet_h = ROWS * SHEET_H + (ROWS - 1) * GAP
    mar_x, mar_y = (210 - sheet_w) / 2, (297 - sheet_h) / 2

    body = ""
    for page in pages:
        body += '<div class="sheet">' + "".join(
            card(l, n, clearance, img, text_y) for n, l in page)
        body += '<div class="cell"></div>' * (per - len(page)) + "</div>\n"

    return f"""<!DOCTYPE html>
<html lang="kk">
<head>
<meta charset="UTF-8">
<title>Вкладыши в боковины</title>
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
  .cell svg {{ position: absolute; left: 0; top: 0;
               width: {SHEET_W:.3f}mm; height: {SHEET_H:.3f}mm; }}

  /* подложка под пожелание: ширина по тексту, поля по бокам 4 мм */
  .banner {{
    position: absolute; left: 50%; transform: translate(-50%, -50%);
    padding: 1.5mm 4mm; white-space: nowrap;
    background: rgba(253,250,243,.94);
    border: 0.32mm solid #c7ab6a; border-radius: 2.4mm;
    font-family: Georgia, "Times New Roman", serif;
    color: #6b4a12; line-height: 1.16;
  }}
  .banner.kk {{ font-size: 6.6mm; }}
  .banner.ru {{ font-size: 4.7mm; }}
</style>
</head>
<body>
{body}</body>
</html>""", len(items), len(pages)


def main():
    ap = argparse.ArgumentParser(description="PDF с треугольными вкладышами в боковины")
    ap.add_argument("--count", type=int, default=7, help="сколько вкладышей (по умолчанию 7)")
    ap.add_argument("--image", default="img/profile-art.jpg",
                    help="файл с картинкой (вертикальный кадр 2:3)")
    ap.add_argument("--text-y", type=float, default=83.0,
                    help="центр плашки с надписью от верха листа, мм (по умолчанию 83)")
    ap.add_argument("--langs", default="kk", help="языки пожелания: kk, ru (по умолчанию kk)")
    ap.add_argument("--clearance", type=float, default=0.4,
                    help="насколько лист меньше рамки, мм всего (по умолчанию 0.4)")
    ap.add_argument("-o", "--out", default=str(HERE / "profile-cards.pdf"))
    a = ap.parse_args()

    langs = [s.strip() for s in a.langs.split(",") if s.strip()]
    bad = [l for l in langs if l not in TEXTS]
    if bad:
        sys.exit(f"нет текста для языка: {', '.join(bad)} (есть: {', '.join(TEXTS)})")

    img = ""
    if a.image:
        f = pathlib.Path(a.image).resolve()
        if not f.exists():
            sys.exit(f"нет файла: {f}")
        img = f.as_uri()

    out = pathlib.Path(a.out).resolve()
    html, n_items, n_pages = build_html(a.count, langs, a.clearance, img, a.text_y)

    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / "profile.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [tool("google-chrome", "chromium", "chromium-browser"),
             "--headless=new", "--disable-gpu", "--no-sandbox",
             "--no-pdf-header-footer", f"--print-to-pdf={out}", page.as_uri()],
            check=True, capture_output=True,
        )

    print(f"вкладышей: {n_items} ({', '.join(langs)}), листов A4: {n_pages} -> {out}")
    print("картинка: " + (a.image if a.image else "нарисована кодом (запасной вариант)"))
    print(f"надпись: центр на {a.text_y:g} мм от верха, окно там шириной "
          f"{2*half_width(a.text_y):.1f} мм")
    print(f"лист: {SHEET_W:.2f} x {SHEET_H:.2f} мм, видно треугольник "
          f"{BASE_R-BASE_L:.2f} x {BASE_Y-APEX[1]:.2f} мм, скрытый низ {HIDDEN_B:.2f} мм")
    print("резать по пунктиру ножницами; печатать в масштабе 100%")


if __name__ == "__main__":
    main()
