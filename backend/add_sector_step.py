import pymysql
import json

conn = pymysql.connect(host='stock_mysql', user='stock_user', password='stock_password', database='stock_pool')
cursor = conn.cursor()

cursor.execute('SELECT steps FROM workflows WHERE id=1')
result = cursor.fetchone()
if result:
    steps_str = result[0]

    if isinstance(steps_str, str):
        steps = json.loads(steps_str)
    else:
        steps = steps_str

    print(f"当前步骤数: {len(steps)}")

    new_step = {
        "type": "match_sector",
        "config": {
            "columns": [],
            "date_str": "2026-04-09",
            "file_path": "",
            "date_column": "",
            "data_source_id": None,
            "output_filename": "2026-04-09.xlsx",
            "apply_formatting": True,
            "exclude_patterns": ["total_", "output_"],
            "stock_code_column": "",
            "use_fixed_columns": True,
            "exclude_patterns_text": "total_,output_",
            "source_dir": "一级板块",
            "new_column_name": "一级板块"
        },
        "status": "pending"
    }
    steps.append(new_step)

    cursor.execute('UPDATE workflows SET steps = %s WHERE id=1', (json.dumps(steps),))
    conn.commit()
    print(f"更新后步骤数: {len(steps)}")
else:
    print("工作流不存在")

cursor.close()
conn.close()