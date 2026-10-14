"""Generate the fictional-data product mock used in this portfolio."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1440, 900
BG = "#F4F7FB"
NAVY = "#10213A"
BLUE = "#356AE6"
TEXT = "#172238"
MUTED = "#68758A"
LINE = "#E3E9F2"
GREEN = "#1D9D6C"
AMBER = "#D98415"
FONT = r"C:\Windows\Fonts\msyh.ttc"


def font(size: int, bold: bool = False):
    path = r"C:\Windows\Fonts\msyhbd.ttc" if bold else FONT
    return ImageFont.truetype(path, size)


def rounded(draw, box, radius=18, fill="white", outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# Sidebar
d.rectangle((0, 0, 250, H), fill=NAVY)
d.text((34, 30), "ChinaList", font=font(30, True), fill="white")
d.text((34, 74), "企业情报订阅", font=font(17), fill="#9FB0C8")
for i, label in enumerate(["概览", "关注企业", "情报摘要", "订阅设置", "账户与隐私"]):
    y = 155 + i * 65
    if label == "订阅设置":
        rounded(d, (20, y - 10, 230, y + 42), 12, "#213B61")
    d.ellipse((38, y + 3, 50, y + 15), fill="#75A2FF" if label == "订阅设置" else "#71839D")
    d.text((66, y - 2), label, font=font(18), fill="white" if label == "订阅设置" else "#C1CCDB")

# Header
d.text((300, 34), "订阅与关注", font=font(29, True), fill=TEXT)
d.text((300, 77), "管理企业清单、摘要频率与隐私授权", font=font(17), fill=MUTED)
rounded(d, (1125, 28, 1400, 82), 14, "white", LINE)
d.text((1152, 44), "demo.user@example.com", font=font(16), fill=TEXT)

# Safety label
rounded(d, (300, 112, 1400, 166), 12, "#FFF8E8", "#F2D28C")
d.text((325, 128), "脱敏交互示意 · Fictional data · 非生产系统截图", font=font(17, True), fill="#8A5A00")

# Cards
rounded(d, (300, 195, 650, 332), 18, "white", LINE)
d.text((328, 220), "个人关注", font=font(18), fill=MUTED)
d.text((328, 255), "3 / 5", font=font(38, True), fill=TEXT)
d.text((470, 270), "家公司", font=font(16), fill=MUTED)

rounded(d, (675, 195, 1025, 332), 18, "white", LINE)
d.text((703, 220), "团队关注", font=font(18), fill=MUTED)
d.text((703, 255), "9 / 15", font=font(38, True), fill=TEXT)
d.text((865, 270), "共享额度", font=font(16), fill=MUTED)

rounded(d, (1050, 195, 1400, 332), 18, "white", LINE)
d.text((1078, 220), "下一期摘要", font=font(18), fill=MUTED)
d.text((1078, 260), "周二 11:00", font=font(27, True), fill=TEXT)
d.text((1078, 300), "Asia/Shanghai", font=font(15), fill=MUTED)

# Watchlist
rounded(d, (300, 360, 920, 845), 18, "white", LINE)
d.text((330, 388), "共享关注企业", font=font(22, True), fill=TEXT)
d.text((330, 425), "团队成员看到同一清单；移除会影响所有成员", font=font(15), fill=MUTED)
companies = [
    ("北辰机器人", "工业机器人 · 新产品信号", "本周 6 条", GREEN),
    ("云岚计算", "AI 基础设施 · 融资动态", "本周 4 条", BLUE),
    ("远洲能源", "储能 · 海外市场", "本周 3 条", AMBER),
    ("星桥医疗", "医疗 AI · 合规政策", "本周 5 条", GREEN),
]
for i, (name, tag, count, color) in enumerate(companies):
    y = 480 + i * 82
    d.line((330, y - 17, 890, y - 17), fill=LINE, width=1)
    rounded(d, (330, y, 370, y + 40), 10, color)
    d.text((342, y + 6), name[0], font=font(19, True), fill="white")
    d.text((390, y - 2), name, font=font(18, True), fill=TEXT)
    d.text((390, y + 27), tag, font=font(14), fill=MUTED)
    rounded(d, (775, y + 2, 878, y + 36), 14, "#EEF4FF")
    d.text((795, y + 10), count, font=font(14), fill=BLUE)

# Preferences
rounded(d, (945, 360, 1400, 845), 18, "white", LINE)
d.text((975, 388), "摘要偏好", font=font(22, True), fill=TEXT)
prefs = [("每周摘要", True), ("重大动态提醒", True), ("每日摘要", False)]
for i, (label, on) in enumerate(prefs):
    y = 468 + i * 65
    d.text((975, y), label, font=font(17), fill=TEXT)
    rounded(d, (1305, y - 4, 1365, y + 28), 16, BLUE if on else "#CED6E2")
    cx = 1348 if on else 1322
    d.ellipse((cx - 12, y, cx + 12, y + 24), fill="white")
d.line((975, 675, 1370, 675), fill=LINE)
d.text((975, 705), "隐私与授权", font=font(18, True), fill=TEXT)
d.text((975, 742), "授权可随时撤回，不改写已保存偏好", font=font(14), fill=MUTED)
rounded(d, (975, 782, 1135, 826), 12, "#F5F7FA", LINE)
d.text((1000, 793), "查看授权", font=font(16), fill=TEXT)

out = Path(__file__).parents[1] / "assets" / "chinalist-sanitized-mock.png"
img.save(out, quality=95)
print(out)

