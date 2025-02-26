import requests
import hashlib
import webbrowser
import json
import xml.etree.ElementTree as ET
import os
from urllib.parse import urlencode
import pyperclip

API_KEY = '1c979bafd82f041b34de0d152493e4f6'
SHARED_SECRET = '3dc21d7e235f6a3db44e840254c18079'

# Function to calculate API Signature
def generate_api_sig(params):
    param_string = ''.join([f"{key}{params[key]}" for key in sorted(params.keys())])
    param_string += SHARED_SECRET
    return hashlib.md5(param_string.encode('utf-8')).hexdigest()

# Step 1: Get the token
def get_token():
    params = {
        'method': 'auth.getToken',
        'api_key': API_KEY,
        'format': 'json'
    }
    params['api_sig'] = generate_api_sig(params)
    
    url = f'http://ws.audioscrobbler.com/2.0/?{urlencode(params)}'
    response = requests.get(url)
    data = json.loads(response.content)
    return data['token']

# Step 2: Authorize the token and get session
def get_session(token):
    auth_params = {
        'api_key': API_KEY,
        'token': token,
        'method': 'auth.getSession'
    }
    auth_params['api_sig'] = generate_api_sig(auth_params)
    
    auth_url = f'http://www.last.fm/api/auth/?{urlencode(auth_params)}'
    webbrowser.open(auth_url)
    
    print("Once you have authorized, press Enter to continue...")
    input()
    
    session_params = {
        'api_key': API_KEY,
        'method': 'auth.getSession',
        'token': token,
    }
    session_params['api_sig'] = generate_api_sig(session_params)
    
    session_url = f'http://ws.audioscrobbler.com/2.0/?{urlencode(session_params)}'
    
    response = requests.get(session_url)
    if response.status_code == 200:
        # Parse XML response
        root = ET.fromstring(response.content)
        # Extract session key from XML
        session_key = root.find('.//key').text
        print(f"Session key: {session_key}")
        return session_key
    else:
        print(f"Failed to get session. Status code: {response.status_code}")
        return None

def copy_to_clipboard(data):
    """将数据复制到剪贴板"""
    pyperclip.copy(data)
    print("数据已复制到剪贴板！")


def main():
    print("请输入 '1' 将数据复制到剪贴板，或输入其他键退出。")

    # 要复制的数据
    data_to_copy = session_key

    while True:
        user_input = input("请输入命令: ").strip()
        if user_input == '1':
            copy_to_clipboard(data_to_copy)  # 复制数据到剪贴板
            print("自动退出程序。")
            break
        else:
            print("退出程序。")
            break

if __name__ == '__main__':
    token = get_token()
    if token:
        session_key = get_session(token)
        if session_key:
            print(f"Session key obtained: {session_key}")
        else:
            print("Failed to obtain session key.")
    else:
        print("Failed to obtain token.")
    
    main()