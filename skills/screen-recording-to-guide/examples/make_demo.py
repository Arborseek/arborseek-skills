"""Create a synthetic UI recording and an UNREVIEWED guide plan in a new directory."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from capture import capture, executable, run


def make_demo(output):
    from PIL import Image, ImageDraw, ImageFont
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        font = ImageFont.truetype('Arial.ttf', 25)
        small = ImageFont.truetype('Arial.ttf', 19)
        title_font = ImageFont.truetype('Arial.ttf', 36)
    except OSError:
        # Modern Pillow includes a scalable default font; old versions use bitmap.
        font = small = title_font = ImageFont.load_default()
    for i in range(1, 4):
        image = Image.new('RGB', (1280, 800), '#f3f6fa')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 1280, 80), fill='#14354b')
        draw.text((35, 22), 'DEMO WORKSPACE', font=font, fill='white')
        draw.text((920, 28), 'demo@example.test', font=small, fill='white')
        draw.rectangle((0, 80, 245, 800), fill='#e4ecf2')
        draw.text((30, 130), 'Projects', font=font, fill='#14354b')
        draw.text((290, 120), 'Projects' if i != 2 else 'New project', font=title_font, fill='#14354b')
        if i == 1:
            draw.rounded_rectangle((970, 112, 1210, 168), radius=8, fill='#176887')
            draw.text((995, 123), 'New project', font=font, fill='white')
            draw.text((300, 265), 'No projects yet', font=font, fill='#526576')
        elif i == 2:
            draw.text((300, 215), 'Project name', font=font, fill='#14354b')
            draw.rounded_rectangle((295, 258, 1130, 325), radius=6, fill='white', outline='#bccbd5', width=2)
            draw.text((315, 277), 'Onboarding guide', font=font, fill='#14354b')
            draw.text((300, 368), 'Description', font=font, fill='#14354b')
            draw.rectangle((295, 410, 1130, 505), fill='white', outline='#bccbd5', width=2)
            draw.text((315, 432), 'Training material', font=font, fill='#14354b')
            draw.rounded_rectangle((920, 570, 1130, 627), radius=8, fill='#176887')
            draw.text((990, 583), 'Save', font=font, fill='white')
        else:
            draw.rounded_rectangle((290, 210, 1195, 265), radius=6, fill='#dcefe3')
            draw.text((310, 224), 'Project created', font=font, fill='#226343')
            draw.rectangle((290, 310, 1195, 405), fill='white', outline='#bccbd5', width=2)
            draw.text((315, 340), 'Onboarding guide', font=font, fill='#14354b')
            draw.text((995, 340), 'Active', font=font, fill='#226343')
        draw.text((290, 746), 'Synthetic interface for testing only', font=small, fill='#617787')
        image.save(output / f'screen-{i:02}.png')
    run([executable('ffmpeg'), '-v', 'error', '-nostdin', '-n', '-framerate', '1/3',
         '-i', str(output / 'screen-%02d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
         '-r', '10', str(output / 'demo.mp4')])
    capture(output / 'demo.mp4', output / 'capture', times=[1, 4, 7])
    plan = {'schema': 'screen-guide/1', 'title': '新建培训项目操作指南',
            'purpose': '在演示工作区中新建一个培训项目，并检查保存结果。',
            'audience': '首次使用项目工作区的员工', 'scope': '演示工作区的项目创建流程',
            'prerequisites': ['已进入演示工作区的 Projects 页面。'],
            'completion': ['项目列表出现 Onboarding guide，状态为 Active。'],
            'sources': {'demo': 'capture/index.json'}, 'coverage_reviewed': False,
            'questions': ['模拟录屏只有三个状态画面，不包含连续点击；请核对示例步骤与图片。'],
            'steps': []}
    texts = [('open', '打开新建项目页面', '在 Projects 页面点击右上角 New project。', '进入 New project 页面。'),
             ('fill', '填写项目信息并保存', '在 Project name 中输入 Onboarding guide，在 Description 中输入 Training material，然后点击 Save。', '页面返回项目列表并显示 Project created。'),
             ('verify', '检查创建结果', '在 Projects 列表中查找 Onboarding guide，检查右侧状态。', '项目名称为 Onboarding guide，状态为 Active。')]
    boxes = [[[970, 112, 240, 56]], [[295, 258, 835, 67], [920, 570, 210, 57]], [[290, 310, 905, 95]]]
    for n, (ident, title, instruction, expected) in enumerate(texts, 1):
        plan['steps'].append({'id': ident, 'title': title, 'instruction': instruction, 'expected': expected,
                              'verified': False, 'privacy_reviewed': False,
                              'evidence': [{'source': 'demo', 'frame': f'f{n:04}', 'role': 'after' if n == 3 else 'before',
                                            'redactions': [[900, 16, 350, 50]], 'boxes': boxes[n-1]}]})
    (output / 'guide.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    make_demo(args.output)
    print('Synthetic recording and UNREVIEWED guide.json created. Do not treat as real workflow validation.')
