import subprocess
import sys
import json
import chardet
import os
import time
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.tmt.v20180321 import tmt_client, models

# 配置项
SECRET_ID = 'xxxx'  # 翻译API的密钥
SECRET_KEY = 'xxxx'  # 翻译API的密钥
NOVEL_FILE_PATH = r'C:\Users\XTY-2\Desktop\学英语小说阅读器\未知\医道官途》（校对版全本）作者：石章鱼\医道官途》（校对版全本）作者：石章鱼 - 未知.txt'  # 导入的整本小说文件
TRANSLATION_DATA_FILE_NAME = 'translation_data.json'  # 存储翻译数据的文件名
CHAPTERS_DIR_NAME = 'chapters'  # 存储分割章节的目录
MAX_CHARS_PER_CHAPTER = 3000  # 每个章节的最大字符数
CHARS_PER_REQUEST = 500  # 每次请求翻译的字符数
REQUEST_DELAY = 1  # 请求间隔时间（秒）

# 默认语言配置
SOURCE_LANGUAGE = 'zh'  # 原文语言，默认为中文
TARGET_LANGUAGE = 'en'  # 译文语言，默认为英文

# 支持的语言代码示例:
# zh (中文), en (英文), jp (日文), fr (法文), es (西班牙文), de (德文), it (意大利文), pt (葡萄牙文)
# 更多语言代码参考腾讯云翻译服务文档: https://cloud.tencent.com/document/product/551/15620

def install_missing_packages(packages):
    """
    安装缺失的Python包。
    
    :param packages: 包名称列表
    """
    try:
        import pkg_resources
    except ImportError:
        print("pkg_resources 未安装。正在安装 setuptools...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'setuptools'])
        import pkg_resources
    
    installed_packages = {pkg.key for pkg in pkg_resources.working_set}
    missing_packages = [pkg for pkg in packages if pkg not in installed_packages]
    
    if missing_packages:
        print(f"检测到缺失的包: {missing_packages}")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
    else:
        print("所有必需的包均已安装。")

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        raw_data = file.read()
        result = chardet.detect(raw_data)
        return result['encoding']

def read_and_split_chapters(file_path, encoding):
    try:
        with open(file_path, 'r', encoding=encoding, errors='replace') as file:
            content = file.read()
    except UnicodeDecodeError:
        print(f"使用 {encoding} 解码失败。尝试 GBK...")
        with open(file_path, 'r', encoding='gbk', errors='replace') as file:
            content = file.read()
    
    chapters = []
    start = 0
    chapter_number = 1
    
    while start < len(content):
        end = start + MAX_CHARS_PER_CHAPTER
        
        # 找到最近的换行符
        if end >= len(content):
            end = len(content)
        else:
            while end < len(content) and content[end] != '\n':
                end += 1
        
        chapter = content[start:end].strip()
        if chapter:
            chapters.append((f"Chapter {chapter_number}", chapter))
            chapter_number += 1
        
        start = end + 1
    
    return chapters

def save_chapter_files(numbered_chapters, chapters_dir):
    if not os.path.exists(chapters_dir):
        os.makedirs(chapters_dir)
    
    for number, chapter in numbered_chapters:
        chapter_file_path = os.path.join(chapters_dir, f"{number}.txt")
        with open(chapter_file_path, 'w', encoding='utf-8') as file:
            file.write(f"# {number}\n\n{chapter}")
        print(f"已保存 {number} 到 {chapter_file_path}")

def translate_lines(lines, secret_id, secret_key, source_language, target_language):
    translated_lines = []
    for i, line in enumerate(lines):
        if line.strip():  # 确保行不为空
            print(f"正在翻译第 {i+1}/{len(lines)} 行: {line[:50]}...")
            translated_line = translate_text(line, secret_id, secret_key, source_language, target_language)
            if translated_line:
                translated_lines.append(translated_line)
                print(f"翻译结果: {translated_line[:50]}...")  # 打印翻译结果
            else:
                translated_lines.append("")  # 如果翻译失败，则追加空字符串
            time.sleep(REQUEST_DELAY)  # 请求之间添加延迟
        else:
            translated_lines.append("")  # 对于空行追加空字符串
    return translated_lines

def translate_text(text, secret_id, secret_key, source_language, target_language):
    try:
        cred = credential.Credential(secret_id, secret_key)
        client = tmt_client.TmtClient(cred, "ap-shanghai")
        
        req = models.TextTranslateRequest()
        params = {
            "SourceText": text,
            "Source": source_language,
            "Target": target_language,
            "ProjectId": 0
        }
        req.from_json_string(json.dumps(params))
        
        resp = client.TextTranslate(req)
        return resp.TargetText
        
    except TencentCloudSDKException as err:
        print(f"翻译错误: {err}")
        return None

def load_translation_data(data_file):
    try:
        with open(data_file, 'r', encoding='utf-8') as file:
            data = json.load(file)
        translated_indices = set(data.get('translated_indices', []))
        return translated_indices
    except FileNotFoundError:
        print(f"{data_file} 未找到。初始化新的翻译数据。")
        return set()

def save_translation_data(translated_indices, data_file):
    data = {
        'translated_indices': list(translated_indices)
    }
    with open(data_file, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)
    print(f"已保存翻译数据到 {data_file}")

def append_translated_chapter(chapter, output_file, translated_chapter):
    number, chapter_text = chapter
    formatted_output = ""
    original_lines = chapter_text.split('\n')
    translated_lines = translated_chapter.split('\n')
    
    max_length = max(len(original_lines), len(translated_lines))
    for i in range(max_length):
        original_line = original_lines[i] if i < len(original_lines) else ""
        translated_line = translated_lines[i] if i < len(translated_lines) else ""
        formatted_output += f"{original_line}\n{translated_line}\n\n"
    
    with open(output_file, 'a', encoding='utf-8') as file:
        file.write(formatted_output)
    print(f"已追加翻译章节 {number} 到 {output_file}")

def calculate_tokens(chapter_text):
    total_chars = sum(len(line) for line in chapter_text.split('\n') if line.strip())
    return total_chars

def main():
    # 检查并安装缺失的依赖
    install_missing_packages(['tencentcloud-sdk-python', 'setuptools'])
    
    # 获取小说文件的目录和文件名
    novel_dir = os.path.dirname(NOVEL_FILE_PATH)
    novel_name = os.path.basename(NOVEL_FILE_PATH)
    translation_data_file = os.path.join(novel_dir, TRANSLATION_DATA_FILE_NAME)
    output_file = os.path.join(novel_dir, f'translated_{novel_name}')
    chapters_dir = os.path.join(novel_dir, CHAPTERS_DIR_NAME)
    
    # 检测文件编码
    encoding = detect_encoding(NOVEL_FILE_PATH)
    print(f"检测到的编码: {encoding}")
    
    # 读取并分割小说内容
    numbered_chapters = read_and_split_chapters(NOVEL_FILE_PATH, encoding)
    print(f"检测到的总章节数: {len(numbered_chapters)}")
    
    # 保存每个章节到单独的文件（仅当文件不存在时）
    if not os.path.exists(chapters_dir):
        save_chapter_files(numbered_chapters, chapters_dir)
    else:
        print(f"章节目录已存在。跳过保存章节。")
    
    # 加载已有的翻译数据
    translated_indices = load_translation_data(translation_data_file)
    print(f"加载的已翻译索引: {translated_indices}")
    
    # 计算未翻译章节的数量和预计消耗的Token数量
    remaining_chapters_count = sum(1 for i in range(len(numbered_chapters)) if i not in translated_indices)
    expected_tokens_mode1 = remaining_chapters_count * MAX_CHARS_PER_CHAPTER
    print(f"估计需要的 Token 数量以翻译所有剩余章节（模式1）: {expected_tokens_mode1}")
    
    # 用户选择翻译模式
    mode = input("请选择翻译模式:\n1. 翻译所有剩余章节\n2. 每次翻译一章\n请输入您的选择 (1/2): ").strip()
    
    if mode == '1':
        # 翻译所有剩余章节
        for i, chapter in enumerate(numbered_chapters):
            number, chapter_text = chapter
            if i in translated_indices:
                print(f"章节 {number} 已翻译。跳过。")
                continue
            
            print(f"\n正在翻译章节 {number}...\n内容: {chapter_text[:200]}...\n")
            lines = chapter_text.split('\n')
            print(f"开始翻译章节 {number}，共 {len(lines)} 行...")
            translated_lines = translate_lines(lines, SECRET_ID, SECRET_KEY, SOURCE_LANGUAGE, TARGET_LANGUAGE)
            translated_chapter = '\n'.join(translated_lines)
            
            # 更新翻译数据
            translated_indices.add(i)
            
            # 保存翻译数据
            save_translation_data(translated_indices, translation_data_file)
            
            # 追加翻译章节到文件
            append_translated_chapter((number, chapter_text), output_file, translated_chapter)
            print(f"翻译章节已追加到 {output_file}")
    elif mode == '2':
        # 按原来的逻辑只翻译单章
        next_chapter_index = 0
        while next_chapter_index < len(numbered_chapters):
            number, chapter = numbered_chapters[next_chapter_index]
            if next_chapter_index in translated_indices:
                print(f"章节 {number} 已翻译。跳过。")
                next_chapter_index += 1
                continue
            
            # 计算当前章节的字符数
            current_chapter_chars = calculate_tokens(chapter[1])
            print(f"估计需要的 Token 数量以翻译章节 {number}: {current_chapter_chars}")
            
            print(f"\n新章节检测到:\n编号: {number}\n内容: {chapter[:200]}...\n")
            user_input = input("您想翻译此章节吗？(y/n): ").strip().lower()
            if user_input == 'y':
                lines = chapter.split('\n')
                print(f"开始翻译章节 {number}，共 {len(lines)} 行...")
                translated_lines = translate_lines(lines, SECRET_ID, SECRET_KEY, SOURCE_LANGUAGE, TARGET_LANGUAGE)
                translated_chapter = '\n'.join(translated_lines)
                
                # 更新翻译数据
                translated_indices.add(next_chapter_index)
                
                # 保存翻译数据
                save_translation_data(translated_indices, translation_data_file)
                
                # 追加翻译章节到文件
                append_translated_chapter((number, chapter), output_file, translated_chapter)
                print(f"翻译章节已追加到 {output_file}")
            else:
                print("跳过此章节。")
            
            next_chapter_index += 1
    else:
        print("无效的选择。退出。")

if __name__ == "__main__":
    main()
