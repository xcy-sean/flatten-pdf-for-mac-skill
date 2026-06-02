# macOS PDF 公章白底修复 Skill

这是一个用于处理 macOS PDF 打印异常的 Codex Skill。

有些 PDF 在 Windows 上显示和打印正常，但在 macOS 预览、Adobe Acrobat for Mac 或实际打印时，公章、签章、水印周围会出现白底、半透明底块，或者打印效果与屏幕显示不一致。这个 Skill 用于将这类 PDF 转换成更适合 macOS 打印的扁平化 PDF。

## 适合解决的问题

- PDF 公章在 Mac 上显示或打印时出现白底。
- Windows 打印正常，但 macOS 打印异常。
- 证书、票据、盖章文件需要在 Mac 上稳定打印。
- 需要批量处理一个目录下的多个 PDF。

## 处理结果

- 保留原 PDF 的页面方向和页面尺寸。
- 不修改源文件，生成新的 PDF。
- 输出文件更适合 macOS 预览和打印。
- 转换后会自动校验，避免只截取到页面局部这类错误结果。

## 安装依赖

推荐先安装 Python 依赖：

```bash
python3 -m pip install reportlab Pillow pypdf PyMuPDF
```

如果当前环境没有 PyMuPDF，脚本会尝试使用 Ghostscript。macOS 可通过 Homebrew 安装：

```bash
brew install ghostscript
```

## 使用方法

转换单个 PDF：

```bash
python3 scripts/flatten_pdf_for_mac.py 输入.pdf 输出_mac打印扁平化.pdf
```

推荐参数：

```bash
python3 scripts/flatten_pdf_for_mac.py 输入.pdf 输出_mac打印扁平化.pdf --dpi 400 --engine auto
```

批量转换：

```bash
mkdir -p output

for pdf in /path/to/source/*.pdf; do
  name="$(basename "$pdf" .pdf)"
  python3 scripts/flatten_pdf_for_mac.py "$pdf" "output/${name}_mac打印扁平化.pdf" --dpi 400 --engine auto
done
```

## 判断是否成功

脚本结束时看到下面这行，表示转换和校验通过：

```text
validation=passed
```

如果校验失败，不建议使用输出 PDF，请根据终端提示检查依赖或源文件。

## 安装为 Codex Skill

将本目录放到：

```text
~/.codex/skills/flatten-pdf-for-mac
```

之后，当遇到 PDF 公章在 Mac 上有白底、Mac 打印异常、需要扁平化 PDF 等问题时，Codex 可以直接使用这个 Skill 处理。
