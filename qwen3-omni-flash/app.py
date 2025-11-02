import os
import gradio as gr
from openai import OpenAI, APIConnectionError
from dotenv import load_dotenv
import tempfile
import base64
import shutil


# 加载环境变量
load_dotenv()

# 初始化DashScope客户端
client = OpenAI(
    timeout=6000,
    api_key=os.environ.get("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# 检查API密钥
api_key = os.environ.get("DASHSCOPE_API_KEY")
if not api_key:
    raise ValueError("请在.env文件中设置DASHSCOPE_API_KEY环境变量")


def process_text_input(user_input, chat_history):
    """处理文本输入"""
    # 添加用户消息到历史记录 (使用字典格式)
    chat_history.append({"role": "user", "content": user_input})

    # 准备消息历史
    messages = []
    for msg in chat_history[:-1]:  # 排除刚刚添加的用户消息
        messages.append(msg)

    # 添加当前用户消息
    messages.append({"role": "user", "content": user_input})

    try:
        # 调用模型
        response = client.chat.completions.create(
            model="qwen3-omni-flash",
            messages=messages,
            stream=True,
            stream_options={"include_usage": True},
        )

        # 流式处理响应
        chat_history[-1] = {"role": "user", "content": user_input}
        assistant_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                assistant_response += content
                # 更新最后一个历史记录项
                if len(chat_history) > 1 and chat_history[-1]["role"] == "assistant":
                    # 如果前一个消息是助手消息，则更新它
                    chat_history[-1] = {
                        "role": "assistant",
                        "content": assistant_response,
                    }
                else:
                    # 否则添加新的助手消息
                    chat_history.append(
                        {"role": "assistant", "content": assistant_response}
                    )
                yield chat_history, None  # 音频文件

        # 返回最终结果
        yield chat_history, None
    except APIConnectionError as e:
        # 网络连接错误处理
        error_msg = "网络连接错误，请检查网络设置或稍后重试。"
        if len(chat_history) > 1 and chat_history[-2]["role"] == "assistant":
            chat_history[-2] = {"role": "assistant", "content": f"助手: {error_msg}"}
        else:
            chat_history.append({"role": "assistant", "content": f"助手: {error_msg}"})
        yield chat_history, None
    except Exception as e:
        # 其他错误处理
        error_msg = f"处理请求时发生错误: {str(e)}"
        if len(chat_history) > 1 and chat_history[-2]["role"] == "assistant":
            chat_history[-2] = {"role": "assistant", "content": f"助手: {error_msg}"}
        else:
            chat_history.append({"role": "assistant", "content": f"助手: {error_msg}"})
        yield chat_history, None
        
# def encode_audio(audio_path):
#     with open(audio_path, "rb") as audio_file:
#         return base64.b64encode(audio_file.read()).decode("utf-8")


def encode_audio(audio_path):
    """安全地读取音频文件并转换为base64编码"""
    try:
        # 创建一个临时副本以避免权限问题
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            with open(audio_path, "rb") as audio_file:
                shutil.copyfileobj(audio_file, tmp_file)
            tmp_file_path = tmp_file.name
        
        # 从临时文件读取并编码
        with open(tmp_file_path, "rb") as audio_file:
            encoded = base64.b64encode(audio_file.read()).decode("utf-8")
        
        # 删除临时文件
        os.unlink(tmp_file_path)
        return encoded
    except Exception as e:
        raise Exception(f"读取音频文件时出错: {str(e)}")

def process_audio_input(audio_file, user_input, chat_history):
    """处理音频输入 不能超过  100MB，时长最长 20 分钟。"""
    if audio_file is None:
        # 如果没有音频文件，但有文本输入，则处理为文本输入
        if user_input:
            # 注意：这里我们需要处理生成器返回的情况
            gen = process_text_input(user_input, chat_history)
            for result in gen:
                yield result
            return
        yield chat_history, None
        return

    # # 读取音频文件
    # with open(audio_file, "rb") as f:
    #     audio_data = f.read()

    # 将音频转换为base64
    base64_audio = encode_audio(audio_file)

    # 添加用户消息到历史记录 (使用字典格式)
    # audio_content = f"[音频输入] {user_input}" if user_input else "[音频输入]"
    # chat_history.append({"role": "user", "content": audio_content})

    # 准备消息历史
    messages = []
    for msg in chat_history[:-1]:  # 排除刚刚添加的用户消息
        messages.append(msg)
 
    # 腾讯云上的文件
    # url = "https://ai-1257405270.cos.ap-guangzhou.myqcloud.com/%E6%B6%88%E9%98%B2%E7%BB%B4%E4%BF%9D.mp3"
   

    try:
        # 调用模型
        response = client.chat.completions.create(
            timeout=6000,
            model="qwen3-omni-flash",
            messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": f"data:;base64,{base64_audio}",
                        "format": "mp3",
                    },
                    
                    ## 经过实践证明， 采用url的方式比采用base64的方式更稳定一些，效率更高。
                    # 直接将文件转base64传给模型，有时会报错，提示网络错误，但是通过url的方式就不会报错。
                    #  "type": "input_audio",
                    #   "input_audio": {
                    #     "data": url,
                    #     "format": "mp3",
                    # },
                },
                {"type": "text", "text": user_input},
            ],
        },
    ],
     
            # 设置输出数据的模态，当前支持两种：["text","audio"]、["text"]
            modalities=["text", "audio"],
            audio={"voice": "Cherry", "format": "wav"},
            # stream 必须设置为 True，否则会报错
            stream=True,
            stream_options={"include_usage": True},
        )
         # 更新最后一个历史记录项
        chat_history.append( {"role": "user", "content": user_input})
        # 流式处理响应
        assistant_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                assistant_response += content
                # print(assistant_response)
                if len(chat_history) > 1 and chat_history[-1]["role"] == "assistant":
                    # 如果前一个消息是助手消息，则更新它
                    chat_history[-1] = {
                        "role": "assistant",
                        "content": assistant_response,
                    }
                else:
                    # 否则添加新的助手消息
                    chat_history.append(
                        {"role": "assistant", "content": assistant_response}
                    )
                yield chat_history, None  # 音频文件

        # 返回最终结果
        yield chat_history, None
    except APIConnectionError as e:
        # 网络连接错误处理
        error_msg = f"网络连接错误，请检查网络设置或稍后重试:{str(e)}"
        print(error_msg)
        if len(chat_history) > 1 and chat_history[-2]["role"] == "assistant":
            chat_history[-2] = {"role": "assistant", "content": f"助手: {error_msg}"}
        else:
            chat_history.append({"role": "assistant", "content": f"助手: {error_msg}"})
        yield chat_history, None
    except Exception as e:
        # 其他错误处理
        error_msg = f"处理音频请求时发生错误: {str(e)}"
        print(error_msg)
        if len(chat_history) > 1 and chat_history[-2]["role"] == "assistant":
            chat_history[-2] = {"role": "assistant", "content": f"助手: {error_msg}"}
        else:
            chat_history.append({"role": "assistant", "content": f"助手: {error_msg}"})
        yield chat_history, None
        


def process_video_input(video_file, user_input, chat_history):
    """处理视频输入 限制为 256 MB，时长限制为 150s；"""
   
    if video_file is None:
        # 如果没有音频文件，但有文本输入，则处理为文本输入
        if user_input:
            # 注意：这里我们需要处理生成器返回的情况
            gen = process_text_input(user_input, chat_history)
            for result in gen:
                yield result
            return
        yield chat_history, None
        return

    # # 读取音频文件
    # with open(video_file, "rb") as f:
    #     audio_data = f.read()

    # 将音频转换为base64
    base64_audio = encode_audio(video_file)

    # 添加用户消息到历史记录 (使用字典格式)
    # audio_content = f"[音频输入] {user_input}" if user_input else "[音频输入]"
    # chat_history.append({"role": "user", "content": audio_content})

    # 准备消息历史
    messages = []
    for msg in chat_history[:-1]:  # 排除刚刚添加的用户消息
        messages.append(msg)
 
    # 腾讯云上的文件
    url = "https://ai-1257405270.cos.ap-guangzhou.myqcloud.com/%E6%B6%88%E9%98%B2%E7%BB%B4%E4%BF%9D.mp3"
   

    try:
        # 调用模型
        response = client.chat.completions.create(
            timeout=6000,
            model="qwen3-omni-flash",
            messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    # "input_audio": {
                    #     "data": f"data:;base64,{base64_audio}",
                    #     "format": "mp3",
                    # },
                    
                    ## 经过实践证明， 采用url的方式比采用base64的方式更稳定一些，效率更高。
                    # 直接将文件转base64传给模型，有时会报错，提示网络错误，但是通过url的方式就不会报错。
                     "type": "input_audio",
                      "input_audio": {
                        "data": url,
                        "format": "mp3",
                    },
                },
                {"type": "text", "text": user_input},
            ],
        },
    ],
     
            # 设置输出数据的模态，当前支持两种：["text","audio"]、["text"]
            modalities=["text", "audio"],
            audio={"voice": "Cherry", "format": "wav"},
            # stream 必须设置为 True，否则会报错
            stream=True,
            stream_options={"include_usage": True},
        )
         # 更新最后一个历史记录项
        chat_history.append( {"role": "user", "content": user_input})
        # 流式处理响应
        assistant_response = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                assistant_response += content
                # print(assistant_response)
                if len(chat_history) > 1 and chat_history[-1]["role"] == "assistant":
                    # 如果前一个消息是助手消息，则更新它
                    chat_history[-1] = {
                        "role": "assistant",
                        "content": assistant_response,
                    }
                else:
                    # 否则添加新的助手消息
                    chat_history.append(
                        {"role": "assistant", "content": assistant_response}
                    )
                yield chat_history, None  # 音频文件

        # 返回最终结果
        yield chat_history, None
    except APIConnectionError as e:
        # 网络连接错误处理
        error_msg = f"网络连接错误，请检查网络设置或稍后重试:{str(e)}"
        print(error_msg)
        if len(chat_history) > 1 and chat_history[-2]["role"] == "assistant":
            chat_history[-2] = {"role": "assistant", "content": f"助手: {error_msg}"}
        else:
            chat_history.append({"role": "assistant", "content": f"助手: {error_msg}"})
        yield chat_history, None
    except Exception as e:
        # 其他错误处理
        error_msg = f"处理音频请求时发生错误: {str(e)}"
        print(error_msg)
        if len(chat_history) > 1 and chat_history[-2]["role"] == "assistant":
            chat_history[-2] = {"role": "assistant", "content": f"助手: {error_msg}"}
        else:
            chat_history.append({"role": "assistant", "content": f"助手: {error_msg}"})
        yield chat_history, None


def clear_history():
    """清空对话历史"""
    return [], None


# 创建Gradio界面
with gr.Blocks(title="Qwen3-Omni-Flash 对话界面") as demo:
    gr.Markdown("# Qwen3-Omni-Flash 对话界面")
    gr.Markdown("与阿里云Qwen3-Omni-Flash模型进行对话，支持文本、音频输入")

    # 聊天历史记录
    chatbot = gr.Chatbot(label="对话历史", type="messages")

    # 文本输入
    with gr.Row():
        text_input = gr.Textbox(
            label="输入文本", placeholder="请输入您的问题...", lines=3
        )
        send_text_btn = gr.Button("发送文本", variant="primary")

    # 文件输入
    with gr.Row():
        with gr.Column():
            audio_input = gr.Audio(label="上传音频", type="filepath")
            send_audio_btn = gr.Button("发送音频")

        with gr.Column():
            video_input = gr.Video(label="上传视频", sources=["upload"])
            send_video_btn = gr.Button("发送视频信息")

    # 控制按钮
    with gr.Row():
        clear_btn = gr.Button("清空对话历史")

    # 事件处理
    send_text_btn.click(
        fn=process_text_input,
        inputs=[text_input, chatbot],
        outputs=[chatbot, gr.Audio(visible=False)],
    ).then(
        fn=lambda: "", inputs=None, outputs=[text_input]  # 清空输入框
    )

    send_audio_btn.click(
        fn=process_audio_input,
        inputs=[audio_input, text_input, chatbot],
        outputs=[chatbot, gr.Audio(visible=False)],
    ).then(
        fn=lambda: (None, ""),  # 清空音频输入和文本输入
        inputs=None,
        outputs=[audio_input, text_input],
    )

    send_video_btn.click(
        fn=process_video_input,
        inputs=[video_input, chatbot],
        outputs=[chatbot, gr.Audio(visible=False)],
    ).then(
        fn=lambda: None, inputs=None, outputs=[video_input]  # 清空视频输入
    )

    clear_btn.click(
        fn=clear_history, inputs=None, outputs=[chatbot, gr.Audio(visible=False)]
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)