import os, json, shutil, urllib.parse

history_dir = os.path.expandvars(r'%APPDATA%\Code\User\History')
project_keyword = 'LivingDocs'
restored_count = 0

print("Đang tự động quét và khôi phục toàn bộ file...")

for root, dirs, files in os.walk(history_dir):
    if 'entries.json' in files:
        try:
            with open(os.path.join(root, 'entries.json'), 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            resource_uri = urllib.parse.unquote(data.get('resource', ''))
            
            if project_keyword.lower() in resource_uri.lower():
                entries = data.get('entries', [])
                if entries:
                    # Lấy bản lưu mới nhất của file
                    latest_entry = entries[-1].get('id')
                    src_file = os.path.join(root, latest_entry)
                    
                    # Xử lý đường dẫn file gốc
                    clean_path = resource_uri.split('///')[-1] if '///' in resource_uri else resource_uri.replace('file://', '')
                    dest_path = os.path.normpath(clean_path)
                    
                    if os.path.exists(src_file):
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(src_file, dest_path)
                        print(f"[Đã khôi phục] -> {dest_path}")
                        restored_count += 1
        except Exception:
            continue

print(f"\n===> HOÀN TẤT! Đã tự động khôi phục {restored_count} file về đúng các thư mục!")