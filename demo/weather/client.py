import asyncio
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 移除 Anthropic 导入
# from anthropic import Anthropic
from dotenv import load_dotenv
import os
import dashscope
import ast


load_dotenv()
def str_to_dict(s):
    """将字符串安全地转换为字典"""
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError) as e:
        print(f"转换失败: {e}")
        return {}


class MCPClient:
    def __init__(self):
        ##初始化会话和客户端对象
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        # 移除 Anthropic 客户端初始化
        # self.anthropic = Anthropic()
        # 设置通义千问 API 密钥
        dashscope.api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not dashscope.api_key:
            raise ValueError("请设置 DASHSCOPE_API_KEY 环境变量")

    async def connect_to_server(self, server_script_path: str):
        """
        连接到MCP服务器
        参数：
        server_script_path: 服务器脚本路径(.py 或 .js)
        """

        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not is_python and not is_js:
            raise ValueError("服务器脚本路径必须是.py或.js文件")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            args=[server_script_path], command=command, env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.writer = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.writer)
        )
        await self.session.initialize()

        ## 列出可用工具
        response = await self.session.list_tools()
        tools = response.tools
        print(f"原始响应: {response}")
        print("\n 已连接到服务器，可用工具:", [tool.name for tool in tools])

   

  
    
    async def process_query(self, query: str) -> str:
        """使用通义千问模型和可用工具处理查询"""
        print(f"处理查询: {query}")
        messages = [{"role": "user", "content": query}]
        response = await self.session.list_tools()
        
        print(f"原始响应: {response}")

        # 转换工具格式以适配通义千问 API 要求
        available_tools = []
        for tool in response.tools:
            available_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",  # 确保描述不为None
                    "parameters": tool.inputSchema or {},   # 确保参数不为None
                }
            })

        print(f"可用工具: {available_tools}")

        # 调用通义千问 API
        try:
            response = dashscope.Generation.call(
                model="qwen-plus-2025-04-28",
                messages=messages,
                tools=available_tools,
                result_format="message"
            )
            
            print(f"初始通义千问响应: {response}")
            
            # 处理响应
            if response.status_code == 200 and "output" in response:
                final_text = []
                output = response["output"]
                
                # 检查是否有工具调用
                if "tool_calls" in output.choices[0].message:
                    for tool_call in output.choices[0].message["tool_calls"]:
                        tool_name = tool_call["function"]["name"]
                        tool_args = tool_call["function"]["arguments"]
                        dict_tool_args = str_to_dict(tool_args)
                        # 执行工具调用
                        print(f"调用工具: {tool_name}，参数: {tool_args}")
                        result = await self.session.call_tool(tool_name, dict_tool_args)
                        
                        # 安全地处理工具调用信息
                        tool_info = f"[工具 {tool_name}，参数: {tool_args}]"
                        final_text.append(tool_info)
                        print(tool_info)
                        
                        # 安全地处理模型初始响应文本
                        initial_text = output.get("text", "") or ""
                        if initial_text:  # 只有当文本非空时才添加
                            messages.append({
                                "role": "assistant", 
                                "content": initial_text, 
                                "tool_calls": [tool_call]
                            })
                        else:
                            messages.append({
                                "role": "assistant", 
                                "content": "", 
                                "tool_calls": [tool_call]
                            })
                        
                        # 安全地处理工具返回内容
                        tool_content = ""
                        if result and hasattr(result, 'content'):
                            tool_content = str(result.content) if result.content is not None else ""
                        
                        messages.append({
                            "role": "tool", 
                            "name": tool_name, 
                            "content": tool_content
                        })
                        
                        # 再次调用模型获取最终响应
                        second_response = dashscope.Generation.call(
                            model="qwen-plus-2025-04-28",
                            messages=messages,
                            result_format="message"
                        )
                        
                        if second_response.status_code == 200 and "output" in second_response:
                            response_text = second_response['output'].choices[0].message
                            stop_flag = second_response['output'].choices[0].finish_reason
                            # 只有当响应文本非空时才添加
                            if stop_flag == 'stop' and response_text:
                                final_text.append(response_text)
                            print(f"模型最终响应: {response_text}")
                        else:
                            error_msg = f"获取模型响应失败: {second_response}"
                            final_text.append(error_msg)
                            print(error_msg)
                else:
                    # 直接返回文本响应
                    direct_text = output.get("text", "") or ""
                    if direct_text:  # 只有当文本非空时才添加
                        final_text.append(direct_text)
                    print(f"直接响应: {direct_text}")
                
                # 关键修复：确保所有元素都是字符串且非None
                safe_strings = []
                for item in final_text:
                    if item is not None:
                        safe_strings.append(str(item))
                    else:
                        safe_strings.append("")  # 将None替换为空字符串
                
                return "\n".join(safe_strings) if safe_strings else "无响应内容"
            else:
                error_msg = f"调用模型失败: {response}"
                print(error_msg)
                return error_msg
        except Exception as e:
            error_msg = f"处理查询时发生错误: {str(e)}"
            print(error_msg)
            import traceback
            traceback.print_exc()  # 打印详细错误信息
            return error_msg

    ### 交互式聊天循环和清理功能
    async def chat_loop(self):
        """交互式聊天循环"""
        print("\nMCP 客户端已启动！")
        print("输入你的查询或 'quit' 退出。")
        print("欢迎使用MCP天气助手！输入'退出'结束会话。")
        while True:
            try:
                query = input("\n查询: ").strip()
                if query.lower() == "quit":
                    break
                if not query:  # 如果输入为空，跳过
                    print("请输入有效的查询内容。")
                    continue
                    
                response = await self.process_query(query)
                print(f"助手: {response}")

            except KeyboardInterrupt:
                print("\n程序被用户中断。")
                break
            except Exception as e:
                error_msg = f"处理查询时出错: {e}"
                print(error_msg)
                # 不要中断循环，继续接受用户输入
                print("助手: 抱歉，处理您的查询时出现了问题，请重试。")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()


async def main():
    """主函数"""
    print(f"MCP 客户端启动中... sys.argv:{sys.argv}")

    if len(sys.argv) != 2:
        print("用法: python client.py <服务器脚本路径>")
        print("示例: python client.py weather.py")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    except Exception as e:
        print(f"连接服务器时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())