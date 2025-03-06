import requests
import json

class WeChatPusher:
    def __init__(self, webhook_url: str):
        """初始化企业微信群机器人推送器
        
        Args:
            webhook_url: 群机器人的webhook地址
        """
        self.webhook_url = webhook_url
        
    def send(self, message: str):
        """发送消息到企业微信群
        
        Args:
            message: 要发送的消息内容
            
        Returns:
            dict: 接口返回结果
        """
        data = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        
        try:
            response = requests.post(
                self.webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'}
            )
            return response.json()
        except Exception as e:
            print(f"发送消息失败: {str(e)}")
            return None 