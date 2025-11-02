# Qwen3-Omni-Flash 对话界面

基于 Gradio 构建的 Web 界面，与阿里云 Qwen3-Omni-Flash 模型进行对话，支持文本、音频输入和流式输出。

## 功能特性

- 支持文本输入和对话
- 支持音频文件上传和处理
- 支持视频文件上传（提示信息）
- 流式响应显示
- 对话历史记录

## 安装依赖

确保您已经安装了所有依赖项：

```bash
uv sync
```

或者使用 pip：

```bash
pip install -r requirements.txt
```

## 环境变量配置

在 `.env` 文件中设置您的 DashScope API Key：

```env
DASHSCOPE_API_KEY=your_api_key_here
```

## 运行应用

```bash
python app.py
```

应用将在 `http://localhost:7860` 启动。

## 使用说明

1. 在文本框中输入您的问题，点击"发送文本"
2. 上传音频文件，点击"发送音频"
3. 上传视频文件，点击"发送视频信息"（当前版本仅提供提示信息）
4. 点击"清空对话历史"可清除所有对话记录

## 注意事项

- 请确保网络连接正常
- 音频文件格式建议使用 WAV 或 MP3
- 视频文件处理功能将在后续版本中完善