import requests
import json
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from colorama import init, Fore, Style
import schedule
import logging
from typing import Dict, List, Tuple
import urllib3
import warnings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

init()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ofc_checkin.log'),
        logging.StreamHandler()
    ]
)

class OFCAutoCheckin:
    def __init__(self, max_workers: int = 3, verbose: bool = False):

        self.session = requests.Session()
        self.base_url = "https://auth.privy.io/api/v1/sessions"
        self.checkin_url = "https://api.deform.cc/"
        self.activity_id = "c326c0bb-0f42-4ab7-8c5e-4a648259b807"
        self.max_workers = max_workers
        self.verbose = verbose
        self.lock = threading.Lock()
        
    def print_status(self, account_index: int, message: str, status: str = 'info'):
        
        if not self.verbose and status == 'info':
            return
        
        colors = {
            'success': Fore.GREEN,
            'error': Fore.RED,
            'info': Fore.BLUE,
            'warning': Fore.YELLOW
        }
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.lock:
            print(f"{colors[status]}[{timestamp}] 账户 {account_index + 1 if account_index >= 0 else ''}: {message}{Style.RESET_ALL}")
            
    def process_account(self, account_data: Tuple[int, str, str, str]):
        
        i, proxy, token, refresh_token = account_data
        
        try:
            self.print_status(i, "开始处理", 'info')
                       
            refresh_response = self.refresh_token(token, refresh_token, proxy)
            if not refresh_response:
                self.print_status(i, "刷新令牌失败", 'error')
                return
                            
            new_token = refresh_response.get('token')
            new_refresh_token = refresh_response.get('refresh_token')
            if new_token and new_refresh_token:
                self.save_tokens(i, new_token, new_refresh_token)
                self.print_status(i, "令牌更新成功", 'success')
            else:
                self.print_status(i, "获取新令牌失败", 'error')
                return
                       
            auth_token = self.get_authorization(new_token, proxy)
            if not auth_token:
                self.print_status(i, "获取authorization失败", 'error')
                return
            
            id_token = refresh_response.get('identity_token')
            if not id_token:
                self.print_status(i, "获取ID令牌失败", 'error')
                return
                
            self.save_id_token(id_token, i)
            
            checkin_response = self.checkin(id_token, proxy, auth_token)
            if checkin_response is None:
                self.print_status(i, "签到失败", 'error')
            
        except Exception as e:
            self.print_status(i, f"处理失败: {str(e)}", 'error')
            logging.error(f"账户 {i+1} 处理失败: {str(e)}")

    def run_batch(self):
        try:
            proxies, tokens, refresh_tokens = self.load_accounts()
            account_data = list(zip(range(len(proxies)), proxies, tokens, refresh_tokens))
            
            print(f"\n{Fore.CYAN}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"开始处理 {len(account_data)} 个账户{Style.RESET_ALL}\n")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                executor.map(self.process_account, account_data)
                
            print(f"\n{Fore.CYAN}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"本轮签到任务完成{Style.RESET_ALL}\n")
            
        except Exception as e:
            logging.error(f"批量处理失败: {str(e)}")
            print(f"{Fore.RED}批量处理失败: {str(e)}{Style.RESET_ALL}")

    def load_accounts(self) -> Tuple[List[str], List[str], List[str]]:
        try:
            with open('proxy.txt', 'r', encoding='utf-8') as f:
                proxies = [line.strip() for line in f if line.strip()]
            
            with open('token.txt', 'r', encoding='utf-8') as f:
                tokens = [line.strip() for line in f if line.strip()]
            
            with open('refreshtoken.txt', 'r', encoding='utf-8') as f:
                refresh_tokens = [line.strip() for line in f if line.strip()]
            
            if not (len(proxies) == len(tokens) == len(refresh_tokens)):
                raise ValueError("代理、token和refresh token的数量不匹配")
            
            self.print_status(-1, f"成功加载 {len(proxies)} 个账户配置", 'info')
            return proxies, tokens, refresh_tokens
            
        except FileNotFoundError as e:
            error_msg = f"配置文件不存在: {str(e)}"
            self.print_status(-1, error_msg, 'error')
            logging.error(error_msg)
            raise
            
        except Exception as e:
            error_msg = f"加载账户配置失败: {str(e)}"
            self.print_status(-1, error_msg, 'error')
            logging.error(error_msg)
            raise

    def refresh_token(self, token: str, refresh_token: str, proxy: str) -> Dict:
        headers = {
            'authority': 'auth.privy.io',
            'accept': 'application/json',
            'accept-language': 'zh-TW,zh;q=0.9',
            'authorization': f'Bearer {token}',
            'content-type': 'application/json',
            'origin': 'https://ofc.onefootball.com',
            'privy-app-id': 'clphlvsh3034xjw0fvs59mrdc',
            'privy-ca-id': '41723ed3-7328-467d-bcd9-166f3e2a7b14',
            'privy-client': 'react-auth:1.80.0-beta-20240821191745',
            'referer': 'https://ofc.onefootball.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        }
        
        data = {
            "refresh_token": refresh_token
        }
        
        proxies = {
            'http': proxy,
            'https': proxy
        }
        
        try:
            self.print_status(-1, f"发送请求到: {self.base_url}", 'info')
            response = self.session.post(
                self.base_url,
                headers=headers,
                json=data,
                proxies=proxies,
                verify=False
            )
            self.print_status(-1, f"响应状态码: {response.status_code}", 'info')
            self.print_status(-1, f"响应内容: {response.text}", 'info')
            return response.json()
        except Exception as e:
            self.print_status(-1, f"刷新令牌失败: {str(e)}", 'error')
            return None

    def save_tokens(self, index: int, token: str, refresh_token: str):
        try:
            with open('token.txt', 'r') as f:
                tokens = f.readlines()
            with open('refreshtoken.txt', 'r') as f:
                refresh_tokens = f.readlines()
            
            while len(tokens) <= index:
                tokens.append('\n')
            while len(refresh_tokens) <= index:
                refresh_tokens.append('\n')
            
            tokens[index] = token + '\n'
            refresh_tokens[index] = refresh_token + '\n'
            
            with open('token.txt', 'w') as f:
                f.writelines(tokens)
            with open('refreshtoken.txt', 'w') as f:
                f.writelines(refresh_tokens)
            
            self.print_status(index, "token和refresh token已更新", 'success')
        except Exception as e:
            self.print_status(index, f"保存token失败: {str(e)}", 'error')

    def save_id_token(self, id_token: str, index: int):
        try:
            try:
                with open('idtoken.txt', 'r') as f:
                    tokens = f.readlines()
            except FileNotFoundError:
                tokens = []
            
            while len(tokens) <= index:
                tokens.append('\n')
            
            tokens[index] = id_token + '\n'
            
            with open('idtoken.txt', 'w') as f:
                f.writelines(tokens)
            
            self.print_status(index, "ID令牌已保存", 'success')
        except Exception as e:
            self.print_status(index, f"保存ID令牌失败: {str(e)}", 'error')

    def get_authorization(self, token: str, proxy: str) -> str:
        headers = {
            'authority': 'api.deform.cc',
            'accept': '*/*',
            'accept-language': 'zh-TW,zh;q=0.9',
            'content-type': 'application/json',
            'origin': 'https://ofc.onefootball.com',
            'referer': 'https://ofc.onefootball.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'x-apollo-operation-name': 'UserLogin'
        }
        
        data = {
            "operationName": "UserLogin",
            "query": "mutation UserLogin($data: UserLoginInput!) {\n  userLogin(data: $data)\n}",
            "variables": {
                "data": {
                    "externalAuthToken": token
                }
            }
        }
        
        proxies = {
            'http': proxy,
            'https': proxy
        }
        
        try:
            response = self.session.post(
                self.checkin_url,
                headers=headers,
                json=data,
                proxies=proxies,
                verify=False
            )
            self.print_status(-1, f"获取authorization响应状态码: {response.status_code}", 'info')
            self.print_status(-1, f"获取authorization响应内容: {response.text}", 'info')
            
            response_data = response.json()
            auth_token = response_data.get('data', {}).get('userLogin')
            if auth_token:
                return auth_token
            else:
                self.print_status(-1, "获取authorization令牌失败", 'error')
                return None
            
        except Exception as e:
            self.print_status(-1, f"获取authorization失败: {str(e)}", 'error')
            return None

    def checkin(self, id_token: str, proxy: str, auth_token: str) -> Dict:
        headers = {
            'authority': 'api.deform.cc',
            'accept': '*/*',
            'accept-language': 'zh-HK,zh;q=0.9,zh-TW;q=0.8',
            'authorization': f'Bearer {auth_token}',
            'content-type': 'application/json',
            'origin': 'https://ofc.onefootball.com',
            'privy-id-token': id_token,
            'referer': 'https://ofc.onefootball.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            'x-apollo-operation-name': 'VerifyActivity'
        }
        
        data = {
            "operationName": "VerifyActivity",
            "query": """
            mutation VerifyActivity($data: VerifyActivityInput!) {
                verifyActivity(data: $data) {
                    record {
                        id
                        activityId
                        status
                        properties
                        createdAt
                        rewardRecords {
                            id
                            status
                            appliedRewardType
                            appliedRewardQuantity
                            __typename
                        }
                        __typename
                    }
                    __typename
                }
            }""",
            "variables": {
                "data": {
                    "activityId": self.activity_id
                }
            }
        }
        
        proxies = {
            'http': proxy,
            'https': proxy
        }
        
        try:
            response = self.session.post(
                self.checkin_url,
                headers=headers,
                json=data,
                proxies=proxies,
                verify=False
            )
            
            if self.verbose:
                self.print_status(-1, f"签到响应状态码: {response.status_code}", 'info')
            
            try:
                response_json = response.json()
                if self.verbose:
                    self.print_status(-1, f"签到响应内容: {json.dumps(response_json, indent=2)}", 'info')
                
                if "errors" in response_json:
                    error_msg = response_json["errors"][0].get("message", "Unknown error")
                    if "Cannot create new campaign spot record" in error_msg:
                        self.print_status(-1, "今日已经签到过了", 'warning')
                        return {"data": {"verifyActivity": {"record": {"status": "ALREADY_CHECKED"}}}}
                    else:
                        self.print_status(-1, f"签到失败: {error_msg}", 'error')
                        return None
                
                record = response_json.get("data", {}).get("verifyActivity", {}).get("record", {})
                status = record.get("status")
                
                if status:
                    if status == "COMPLETED":
                        rewards = record.get("rewardRecords", [])
                        reward_info = []
                        for reward in rewards:
                            reward_type = reward.get("appliedRewardType")
                            reward_quantity = reward.get("appliedRewardQuantity")
                            if reward_type and reward_quantity:
                                reward_info.append(f"{reward_type}: {reward_quantity}")
                        
                        if reward_info:
                            self.print_status(-1, f"签到成功! 获得奖励: {', '.join(reward_info)}", 'success')
                        else:
                            self.print_status(-1, "签到成功!", 'success')
                    elif status == "ALREADY_CHECKED":
                        self.print_status(-1, "今日已经签到过了", 'warning')
                    else:
                        self.print_status(-1, f"签到状态: {status}", 'info')
                    
                    return response_json
                else:
                    self.print_status(-1, "签到响应中没有状态信息", 'error')
                    return None
                
            except json.JSONDecodeError:
                self.print_status(-1, f"解析响应失败: {response.text}", 'error')
                return None
            
        except Exception as e:
            self.print_status(-1, f"签到请求失败: {str(e)}", 'error')
            return None

def run_scheduler():
    auto_checkin = OFCAutoCheckin(max_workers=3)  
    
    def job():
        print(f"\n{Fore.YELLOW}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
              f"开始执行定时签到任务{Style.RESET_ALL}")
        auto_checkin.run_batch()
    
    schedule.every(12).hours.do(job)
    
    job()
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  
        except Exception as e:
            logging.error(f"定时任务异常: {str(e)}")
            print(f"{Fore.RED}定时任务异常: {str(e)}{Style.RESET_ALL}")
            time.sleep(300)  

if __name__ == "__main__":
    try:
        print(f"""{Fore.CYAN}
╔══════════════════════════════════════════╗
║           OFC_S2 Auto Checkin            ║
╚══════════════════════════════════════════╝
{Style.RESET_ALL}""")
        
        auto_checkin = OFCAutoCheckin(max_workers=3, verbose=True)
        run_scheduler()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}程序已停止运行{Style.RESET_ALL}")
    except Exception as e:
        logging.error(f"程序异常: {str(e)}")
        print(f"{Fore.RED}程序异常: {str(e)}{Style.RESET_ALL}")
