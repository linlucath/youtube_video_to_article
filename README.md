## 用途

将英文的 youtube 视频转为中英互译的文章, 从而方便学习. 经不完全测试, 使用美国节点能显著提高下载字幕的成功率.

## 使用方式

1. 根据 config.yml.example 完成 config.yml

2. 设置环境变量 DEEPSEEK_API_KEY

3. 获取 cookies.txt 文件, 可使用浏览器插件" Cookie-Editor"导出, 格式为 Netscape, 保存至 ./tools/cookies.txt

4. 执行 
```bash
pip install -r requirements.txt
cd tools
python ./main.py --youtube_link "{{youtube视频链接/ID}}"
```
## 其他

1. --youtube_link 可使用 -l 代替

2. 处理完成后需将 output/ raw/ 目录下的文件手动删除, 否则下次处理同一视频时会跳过下载字幕和翻译步骤.

3. 当提示字幕下载失败时, 可尝试更新一下 cookies.txt 文件.

## 效果展示

-视频: https://www.youtube.com/watch?v=dUzLD91Sj-o&list=PL5-TkQAfAZFbzxjBHtzdVCWE0Zbhomg7r
-文章: https://linlucath.github.io/blog/lecture-12_-recurrent-networks_en/lecture-12_-recurrent-networks_en

## 费用估计
处理一段 1小时20分钟, 视频大约耗费 0.2RMB
