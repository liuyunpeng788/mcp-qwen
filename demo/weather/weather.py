from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

## 初始化FastMCP服务器
mcp = FastMCP("weather")

# 常量
NWS_API_BASE = "https://api.weather.gov"
USER_AGENT = "weather-app/1.0"

async def make_nws_request(url: str) ->  dict[str, Any] | None:
    """向NWS API 发出get请求，处理错误并返回JSON响应 """
    headers = {"User-Agent": USER_AGENT,
               "Accept": "application/geo+json"}
    async with httpx.AsyncClient() as client:
        try:
            print(f"请求URL: {url}")
            response = await client.get(url, headers=headers,timeout=30)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP错误: {e}")
            return None
        except httpx.RequestError as e:
            print(f"请求错误: {e}")
            return None
        except Exception as e:
            print(f"其他错误: {e}")
            return None

def format_alert(feature:dict)->str:
    """将劲爆特征格式化为可读字符串"""
    props = feature["properties"]
    return f"""
        预警类型: {props.get("event","未知")}
        预警等级: {props.get("severity","未知")}
        预警描述: {props.get("description","未知")}
        预警区域: {props.get("areaDesc","未知")}
        预警发布时间: {props.get("effective","未知")}
        预警指令: {props.get("instruction","未知")}
        """


@mcp.tool()
async def get_alerts(state:str)->str:
    """获取指定州的天气警报（使用两字母州代码如CA/NY）"""
    url = f"{NWS_API_BASE}/alerts/active/area/{state}"
    data = await make_nws_request(url)
    
    if not data or "features" not in data :
        return "无法获取警报或者未找到警报"
    
    if not data["features"]:
        return "未找到该州的天气警报"
    
    alerts = [format_alert(feature) for feature in data["features"]]
    return "\n----\n".join(alerts)

@mcp.tool()
async def get_forecast(latitude:float,longitude:float) ->str:
    """获取位置的天气预报
    args: 
        latitude: 纬度（例如34.0522）
        longitude: 经度（例如-118.2437）    
    """
    ## 首先获取预报网格端点
    points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
    print(f"获取预报网格端点URL: {points_url}")
    points_data=await make_nws_request(points_url)
    
    if not points_data:
        return "无法为此位置获取预报数据"
    
    #从点响应中获取预报URL
    forecast_url = points_data["properties"]["forecast"]
    forecast_data=await make_nws_request(forecast_url)
    if not forecast_data:
        return "无法获取详细预报"
    
    # 将时段格式化为可读预报
    periods= forecast_data["properties"]["periods"]
    forecasts = []
    for period in periods[:5]:
        forecast = f"""
        {   period['name']}:
            Temperature: {period['temperature']}°{period['temperatureUnit']}
            Wind: {period['windSpeed']} {period['windDirection']}
            Forecast: {period['detailedForecast']
        }
        """
        forecasts.append(forecast)
    return "\n----\n".join(forecasts)

def test_tool_decorator():
    """测试工具装饰器是否可用"""
    mcp = FastMCP("TestServer")
    
    try:
        # 测试装饰器
        @mcp.tool()
        async def test_tool():
            return "测试成功"
            
        print("✅ 工具装饰器工作正常")
        return True
    except Exception as e:
        print(f"❌ 工具装饰器失败: {e}")
        return False

 
if __name__ == "__main__":
    # test_tool_decorator()
    # print("weather server start")
    ##初始化并运行服务器
    mcp.run(transport='stdio')
    
    
    
    
