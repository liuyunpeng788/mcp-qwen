import asyncio
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


class MCPClient:
    def __init__(self):
        ##初始化会话和客户端对象
        self.session : Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()    
            
    async def connect_to_server(self,server_script_path:str):
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
            args=[server_script_path],
            command=command,
            env = None 
        )
        
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio,self.writer = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio,self.writer)
        )
        await self.session.initialize()
        
        ## 列出可用工具
        response = await self.session.list_tools()
        tools = response.tools
        print(f"原始响应: {response}")
        print("\n 已连接到服务器，可用工具:",[tool.name for tool in tools])
        
        
    async def process_query(self,query:str) ->str:
        """使用claude 和可用工具处理查询"""
        print(f"处理查询: {query}")
        messages = [{
            "role": "user",
            "content": query
        }]
        response = await self.session.list_tools()
        
        
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools ]  
        
        print(f"可用工具: {available_tools}")
        
        ##初始 claude api调用
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1024,
            messages=messages,
            tools=available_tools
        )
        
        ## 处理相应和工具调用
        tool_results = []
        final_text = []
        
        assistant_message_content=[]
        print(f"初始 claude 响应: {response.content}")
        
        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)
                assistant_message_content.append(content.text)
            elif content.type == "tool_use":
                tool_name = content.name
                tool_args = content.input
                
                ## 执行工具调用
                result = await self.session.call_tool(tool_name,tool_args)
                tool_results.append({"call":tool_name,"result":result})
                final_text.append(f"[工具 {tool_name}，参数: {tool_args}]")
                
                assistant_message_content.append(content)
                messages.append({
                    "role": "assistant",
                    "content": assistant_message_content
                })
                
                messages.append({
                    "role": "user",
                    "content": [{"type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content}]
                })
                
                ## 获取claude 的下一个响应
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1024,
                    messages=messages,
                    tools=available_tools
                )
                print(f"claude 响应: {response.content}")
                
                final_text.append(response.content[0].text)
                
                return "\n".join(final_text)
            

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
                response = await self.process_query(query)
                print(f"助手: {response}")
                
            except Exception as e:
                print(f"处理查询时出错: {e}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()
    

async def main():
 
    """主函数"""
    if len(sys.argv) != 2:
        print("用法: python client.py <服务器脚本路径>")
        sys.exit(1)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()
    
if __name__ == "__main__":
    import sys
    asyncio.run(main()) 
    