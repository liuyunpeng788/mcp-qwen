import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# 初始化DashScope客户端
client = OpenAI(
    # API密钥从环境变量获取
    api_key=os.environ.get("DASHSCOPE_API_KEY"),
    # DashScope API基础URL
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 检查API密钥是否正确加载
api_key = os.environ.get("DASHSCOPE_API_KEY")
if not api_key:
    print("错误: 未找到DASHSCOPE_API_KEY环境变量")
    print("请确保在.env文件中设置了DASHSCOPE_API_KEY")
    exit(1)

print(f"API Key loaded: {api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "API Key loaded")

try:
    # 创建聊天完成请求
    completion = client.chat.completions.create(
        model="qwen3-omni-flash",
        messages=[{"role": "user", "content": "中国面积最大的省"}],
        # 设置输出数据的模态，当前支持两种：["text","audio"]、["text"]
        modalities=["text", "audio"],
        audio={"voice": "Cherry", "format": "wav"},
        # 流式传输必须设置为 True
        stream=True,
        stream_options={"include_usage": True},
    )

    # 处理流式响应
    print("Assistant: ", end="", flush=True)
    audio_data = b""
    
    for chunk in completion:
        if chunk.choices:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                
            # 收集音频数据（如果有）
            if hasattr(chunk.choices[0].delta, 'audio') and chunk.choices[0].delta.audio:
                audio_data += chunk.choices[0].delta.audio.data
                
        # 打印使用情况（如果有的话）
        if hasattr(chunk, 'usage') and chunk.usage:
            print(f"\n\nToken 使用情况: {chunk.usage}")
            
    print()  # 添加换行
    
    # 如果有音频数据，保存到文件
    if audio_data:
        with open("response.wav", "wb") as f:
            f.write(audio_data)
        print("音频已保存到 response.wav")
        
except Exception as e:
    print(f"\n发生错误: {e}")
    print("请检查:")
    print("1. DASHSCOPE_API_KEY 是否正确设置")
    print("2. 网络连接是否正常")
    print("3. 模型名称是否正确")