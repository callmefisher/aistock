# 工作流类型系统 - 部署指南

## 📋 变更内容

### 1. 新增功能
- ✅ 支持多种工作流类型（并购重组、股权转让）
- ✅ 不同类型使用不同的数据目录和命名规则
- ✅ 用户可在UI中选择工作流类型
- ✅ 支持未来扩展新类型

### 2. 文件变更
- **新增文件**：
  - `config/workflow_type_config.py` - 配置中心
  - `services/path_resolver.py` - 路径解析器
  - `tests/test_workflow_type_system.py` - 单元测试（30个测试用例）
  - `scripts/add_workflow_type_column.sql` - SQL迁移脚本
  - `scripts/migrate_add_workflow_type.py` - Python迁移脚本

- **修改文件**：
  - `models/models.py` - 添加 `workflow_type` 字段
  - `services/workflow_executor.py` - 接入路径解析器
  - `api/workflows.py` - 支持类型CRUD和传递

---

## 🚀 部署步骤

### 步骤1: 数据库迁移

**方法A：使用SQL脚本（推荐）**
```bash
# 连接到MySQL数据库
mysql -u stock_user -p stock_pool

# 执行迁移脚本
source /Users/xiayanji/qbox/aistock/backend/scripts/add_workflow_type_column.sql
```

**方法B：直接执行SQL**
```sql
USE stock_pool;

ALTER TABLE workflows
ADD COLUMN workflow_type VARCHAR(50) DEFAULT ''
COMMENT '工作流类型: 空/并购重组/股权转让/...'
AFTER description;
```

**方法C：使用Python脚本（需要安装依赖）**
```bash
cd /Users/xiayanji/qbox/aistock/backend
pip install aiomysql pymysql
python scripts/migrate_add_workflow_type.py
```

### 步骤2: 验证迁移

```sql
-- 检查字段是否添加成功
DESC workflows;

-- 应该看到类似输出：
-- workflow_type | varchar(50) | YES | | '' | 工作流类型...
```

### 步骤3: 重启后端服务

```bash
# 如果使用Docker
docker-compose restart backend

# 如果直接运行
pkill -f "uvicorn main:app"
python main.py
```

### 步骤4: 验证API

```bash
# 获取可用的工作流类型
curl http://localhost:8000/api/workflows/types/

# 预期返回：
{
  "success": true,
  "types": [
    {"value": "", "display_name": "默认（并购重组）"},
    {"value": "股权转让", "display_name": "股权转让"}
  ]
}
```

---

## 📊 功能验证

### 测试1: 创建"股权转让"类型工作流

```bash
curl -X POST http://localhost:8000/api/workflows/ \
-H "Content-Type: application/json" \
-H "Authorization: Bearer YOUR_TOKEN" \
-d '{
  "name": "股权转让数据处理",
  "description": "每日股权转让数据自动化处理",
  "workflow_type": "股权转让",
  "steps": [
    {"type": "merge_excel", "config": {"date_str": "2026-04-12"}},
    {"type": "smart_dedup", "config": {}},
    {"type": "extract_columns", "config": {}},
    {"type": "match_high_price", "config": {}},
    {"type": "match_ma20", "config": {}},
    {"type": "match_soe", "config": {}},
    {"type": "match_sector", "config": {}}
  ]
}'
```

**预期结果**：
- 数据上传目录: `/data/excel/股权转让/2026-04-12`
- 公共数据目录: `/data/excel/股权转让/public`
- 最终输出文件: `股权转让20260412.xlsx`

### 测试2: 运行单元测试

```bash
cd /Users/xiayanji/qbox/aistock/backend
python -m pytest tests/test_workflow_type_system.py -v

# 应该看到：30 passed in 0.06s
```

---

## 🎯 使用指南

### 前端集成

#### 1. 获取类型列表
```javascript
const response = await fetch('/api/workflows/types/');
const { types } = await response.json();

// types = [
//   {value: "", display_name: "默认（并购重组）"},
//   {value: "股权转让", display_name: "股权转让"}
// ]
```

#### 2. 创建工作流时选择类型
```jsx
<select name="workflow_type">
  {types.map(type => (
    <option key={type.value} value={type.value}>
      {type.display_name}
    </option>
  ))}
</select>
```

#### 3. 编辑已有工作流的类型
```javascript
await fetch(`/api/workflows/${workflowId}`, {
  method: 'PUT',
  body: JSON.stringify({ workflow_type: '股权转让' })
});
```

---

## 🔧 后续扩展

### 添加新类型（例如："定增"）

编辑 `config/workflow_type_config.py`：

```python
WORKFLOW_TYPE_CONFIG["定增"] = {
    "display_name": "定增",
    "base_subdir": "定增",
    "directories": {
        "upload_date": "定增/{date}",
        "public": "定增/public",
    },
    "naming": {
        "output_template": "定增{date}.xlsx",
        # ... 其他配置
    },
    "match_sources": {
        # 可选择复用或定制化
    }
}
```

**无需重启服务**，前端会自动显示新选项！

### 重命名现有类型

**方法A：直接修改key（无历史数据）**
```python
# 将"股权转让"改为"投融资"
"投融资": {  # 原来的key是"股权转让"
    "display_name": "投融资",
    # ... 其他配置
}
```

**方法B：使用别名（有历史数据）**
```python
TYPE_ALIASES = {
    "股权转让": "投融资",  # 旧名称映射到新配置
}
```

---

## ⚠️ 注意事项

1. **向后兼容**：
   - 已有的工作流不设置type → 自动使用默认流程
   - 空字符串或"并购重组" → 走老流程，行为完全不变

2. **目录创建**：
   - 系统会自动创建所需目录
   - 确保数据目录有写入权限

3. **数据迁移**：
   - 如果已有"融资"类型的工作流数据，需要手动迁移目录：
     ```bash
     mv /data/excel/融资 /data/excel/股权转让
     ```

4. **前端适配**：
   - 建议在工作流编辑表单添加类型选择器
   - 对于match_sector步骤，提示用户"最终输出将根据类型自动命名"

---

## 📞 支持

如有问题，请检查：
1. 数据库字段是否添加成功
2. 后端服务是否正常启动
3. 测试是否全部通过
4. API返回的类型列表是否正确

---

## 📝 变更日志

**2026-04-12**
- ✅ 将"融资"重命名为"股权转让"
- ✅ 完成数据库迁移脚本
- ✅ 所有单元测试通过（30/30）
- ✅ 向后兼容验证通过
