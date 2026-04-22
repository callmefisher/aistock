<template>
  <div class="workflows">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>工作流列表</span>
          <div class="header-actions">
            <el-button type="warning" @click="handleBatchRun" :disabled="selectedWorkflows.length === 0 || batchExecuting">
              <el-icon><Promotion /></el-icon>
              一键并行执行 ({{ selectedWorkflows.length }})
            </el-button>
            <el-button type="primary" @click="openCreateDialog">
              <el-icon><Plus /></el-icon>
              创建工作流
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="workflows" stripe v-loading="loading" @selection-change="handleSelectionChange" ref="workflowTableRef" :row-class-name="getRowClassName">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="工作流名称" />
        <el-table-column label="类型" width="180">
          <template #default="{ row }">
            {{ row.workflow_type || '并购重组' }}
          </template>
        </el-table-column>
        <el-table-column label="数据日期" width="110">
          <template #default="{ row }">
            {{ row.date_str || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" />
        <el-table-column label="操作" width="300">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="handleRun(row)">
              执行
            </el-button>
            <el-button size="small" @click="handleViewSteps(row)">
              步骤
            </el-button>
            <el-button size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" :title="isEditing ? '编辑工作流' : '创建工作流'" width="800px" @close="onEditDialogClose">
      <el-form :model="form" label-width="140px">
        <el-form-item label="工作流名称">
          <el-input v-model="form.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item v-if="isEditing" label="创建时间">
          <el-input :model-value="formatBeijingTime(form.created_at)" disabled />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="2" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="工作流类型">
          <el-select v-model="form.workflow_type" style="width: 100%" placeholder="请选择工作流类型">
            <el-option
              v-for="type in workflowTypes"
              :key="type.value"
              :label="type.display_name"
              :value="type.value"
            />
          </el-select>
          <el-alert
            v-if="form.workflow_type === '股权转让'"
            title="股权转让类型将使用独立的数据目录和输出文件命名"
            type="info"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '增发实现'"
            title="增发实现类型将使用独立的数据目录，上市公告日将映射为最新公告日"
            type="info"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '申报并购重组'"
            title="申报并购重组类型将使用独立的数据目录，更新日期将映射为最新公告日"
            type="info"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '减持叠加质押和大宗交易'"
            title="减持叠加质押和大宗交易类型将使用独立的数据目录，证券名称映射为证券简称，最新大股东减持公告日期映射为最新公告日"
            type="info"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '招投标'"
            title="招投标类型将使用独立的数据目录，证券名称映射为证券简称，发生日期映射为最新公告日"
            type="info"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '条件交集'"
            title="条件交集类型：聚合所有其他工作流的最终输出，按过滤条件筛选后合并输出，并计算交集生成选股池"
            type="warning"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '导出20日均线趋势'"
            title="导出20日均线趋势：复用统计分析的趋势导出逻辑，生成含折线图的Excel，不写入数据库"
            type="warning"
            :closable="false"
            style="margin-top: 8px"
          />
          <el-alert
            v-if="form.workflow_type === '涨幅排名'"
            title="涨幅排名：按第2列降序排名，自动对比上一工作日数据，Top5深红标注，排名提升浅红标注"
            type="info"
            :closable="false"
            style="margin-top: 8px"
          />
        </el-form-item>

        <el-divider content-position="left">工作流步骤</el-divider>

        <div class="steps-container">
          <div v-for="(step, index) in form.steps" :key="index" class="step-item">
            <el-card shadow="hover" class="step-card">
              <template #header>
                <div class="step-header">
                  <el-tag type="success" size="small">步骤 {{ index + 1 }}</el-tag>
                  <el-tag :type="getStepType(step.type)" size="small">{{ getStepTypeName(step.type) }}</el-tag>
                  <el-button link type="danger" size="small" @click="removeStep(index)" :disabled="form.steps.length <= 1">
                    删除
                  </el-button>
                </div>
              </template>

              <el-form-item label="步骤类型">
                <el-select v-model="step.type" style="width: 100%" @change="onStepTypeChange(step, index)" :disabled="isAggregationType || form.workflow_type === '涨幅排名'">
                  <template v-if="form.workflow_type === '条件交集'">
                    <el-option label="合并当日数据" value="condition_intersection" />
                  </template>
                  <template v-else-if="form.workflow_type === '导出20日均线趋势'">
                    <el-option label="导出趋势Excel" value="export_ma20_trend" />
                  </template>
                  <template v-else-if="form.workflow_type === '涨幅排名'">
                    <el-option label="合并当日数据源" value="merge_excel" />
                    <el-option label="涨幅排名排序" value="ranking_sort" />
                  </template>
                  <template v-else>
                    <el-option label="导入Excel" value="import_excel" />
                    <el-option label="合并当日数据源" value="merge_excel" />
                    <el-option label="智能去重" value="smart_dedup" />
                    <el-option label="提取列" value="extract_columns" />
                    <el-option label="导出Excel" value="export_excel" />
                    <el-option label="匹配百日新高" value="match_high_price" />
                    <el-option label="匹配20日均线" value="match_ma20" />
                    <el-option label="匹配国企" value="match_soe" />
                    <el-option label="匹配一级板块" value="match_sector" />
                    <el-option
                      v-if="form.workflow_type === '质押'"
                      label="质押异动和趋势"
                      value="pledge_trend_analysis"
                    />
                    <el-option label="待定" value="pending" />
                  </template>
                </el-select>
              </el-form-item>

              <template v-if="step.type === 'import_excel'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="选择文件">
                  <div class="file-input-wrapper">
                    <el-input v-model="step.config.file_path" placeholder="请选择或输入文件名" readonly />
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      @change="onFileSelect($event, step)"
                      class="file-input"
                    />
                    <el-button @click="triggerFileInput(index)" class="file-btn">
                      选择文件
                    </el-button>
                  </div>
                </el-form-item>
                <el-form-item label="或选择数据源">
                  <el-select v-model="step.config.data_source_id" style="width: 100%" placeholder="请选择数据源" clearable>
                    <el-option
                      v-for="ds in dataSources"
                      :key="ds.id"
                      :label="ds.name"
                      :value="ds.id"
                    />
                  </el-select>
                </el-form-item>
              </template>

              <template v-if="step.type === 'merge_excel'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                    @change="onMergeDateChange(step, index)"
                  />
                </el-form-item>
                <el-form-item label="上传数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="info">目标目录: {{ getTargetDirDisplay('merge_excel', step.config.date_str) }}</el-tag>
                    </div>
                    <div class="upload-actions">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        :id="`file-input-${index}`"
                        @change="handleFileUpload($event, step, index)"
                        style="display: none"
                      />
                      <el-button
                        type="primary"
                        size="small"
                        @click="triggerFileInput(index)"
                        :loading="uploadingSteps.has(`step_${index}`)"
                      >
                        <el-icon><Upload /></el-icon>
                        上传Excel文件
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="上传公共数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="warning">公共目录: {{ getPublicDirDisplay() }} {{ form.workflow_type === '涨幅排名' ? '(存放历史文件，不参与合并)' : '(与当日数据一起合并)' }}</el-tag>
                    </div>
                    <div class="upload-actions">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        :id="`public-file-input-${index}`"
                        @change="handlePublicFileUpload($event, step, index)"
                        style="display: none"
                      />
                      <el-button
                        type="warning"
                        size="small"
                        @click="triggerPublicFileInput(index)"
                        :loading="uploadingSteps.has(`public_${index}`)"
                      >
                        <el-icon><Upload /></el-icon>
                        上传到公共目录
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="公共文件列表" v-if="step.type === 'merge_excel'">
                  <div class="uploaded-files-list" v-if="publicFiles[`step_${index}`]?.length > 0">
                    <div v-for="file in publicFiles[`step_${index}`]" :key="file.path" class="file-item">
                      <div class="file-info">
                        <el-icon><Document /></el-icon>
                        <span class="file-name">{{ file.filename }}</span>
                        <span class="file-size">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <div class="file-actions">
                        <el-button size="small" link @click="previewPublicFile(file.path)">
                          <el-icon><View /></el-icon>
                        </el-button>
                        <el-button size="small" link type="danger" @click="deletePublicFile(file.path, step, index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="已上传文件" v-if="['import_excel', 'merge_excel', 'match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)">
                  <div class="uploaded-files-list" v-if="uploadedFiles[`step_${index}`]?.length > 0">
                    <div v-for="file in uploadedFiles[`step_${index}`]" :key="file.path" class="file-item">
                      <div class="file-info">
                        <el-icon><Document /></el-icon>
                        <span class="file-name">{{ file.filename }}</span>
                        <span class="file-size">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <div class="file-actions">
                        <el-button size="small" link @click="previewFile(file.path)">
                          <el-icon><View /></el-icon>
                        </el-button>
                        <el-button size="small" link type="danger" @click="deleteUploadedFile(file.path, step, index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="默认: total_1.xlsx" />
                </el-form-item>
                <el-form-item label="排除文件名">
                  <el-input
                    v-model="step.config.exclude_patterns_text"
                    placeholder="多个用逗号分隔，如: total_,output_,temp_"
                    @blur="onExcludePatternsChange(step)"
                  />
                </el-form-item>
                <el-alert :title="`合并当日目录和 ${getPublicDirDisplay()} 目录下所有Excel文件`" type="info" :closable="false" />
              </template>

              <template v-if="step.type === 'smart_dedup'">
                <el-form-item label="证券代码列">
                  <el-input v-model="step.config.stock_code_column" placeholder="自动检测或手动输入列名" />
                </el-form-item>
                <el-form-item label="日期列">
                  <el-input v-model="step.config.date_column" placeholder="自动检测或手动输入列名" />
                </el-form-item>
                <el-alert title="按证券代码去重，保留最新公告日的数据" type="success" :closable="false" />
              </template>

              <template v-if="step.type === 'extract_columns'">
                <el-form-item label="选择模式">
                  <el-radio-group v-model="step.config.use_fixed_columns" @change="onColumnModeChange(step)">
                    <el-radio :value="true">
                      {{ form.workflow_type === '质押' ? '固定列（含来源+3预判列）' : '固定4列' }}
                    </el-radio>
                    <el-radio :value="false">自定义列</el-radio>
                  </el-radio-group>
                </el-form-item>

                <template v-if="step.config.use_fixed_columns !== false">
                  <el-alert
                    v-if="form.workflow_type === '质押'"
                    title="提取: 序号、证券代码、证券简称、最新公告日、来源、持续递增（一年内）、持续递减（一年内）、质押异动"
                    type="success" :closable="false"
                  />
                  <el-alert
                    v-else
                    title="提取: 序号、证券代码、证券简称、最新公告日"
                    type="success" :closable="false"
                  />
                </template>
                <template v-else>
                  <el-form-item label="选择列">
                    <el-select v-model="step.config.columns" multiple filterable allow-create
                               style="width: 100%" placeholder="选择要提取的列（可输入自定义）">
                      <el-option label="序号" value="序号" />
                      <el-option label="证券代码" value="证券代码" />
                      <el-option label="证券简称" value="证券简称" />
                      <el-option label="最新公告日" value="最新公告日" />
                      <template v-if="form.workflow_type === '质押'">
                        <el-option label="来源" value="来源" />
                        <el-option label="持续递增（一年内）" value="持续递增（一年内）" />
                        <el-option label="持续递减（一年内）" value="持续递减（一年内）" />
                        <el-option label="质押异动" value="质押异动" />
                      </template>
                    </el-select>
                  </el-form-item>
                  <el-alert
                    v-if="form.workflow_type === '质押'"
                    title="质押类型：即便未显式勾选，后端仍会自动保留已存在的「来源/持续递增/持续递减/质押异动」以免信息丢失"
                    type="info" :closable="false"
                  />
                  <el-alert
                    v-else
                    title="提示: 可直接输入自定义列名并回车添加"
                    type="info" :closable="false"
                  />
                </template>

                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="默认: output_1.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'export_excel'">
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="请输入输出文件名" />
                </el-form-item>
                <el-form-item label="应用格式化">
                  <el-switch v-model="step.config.apply_formatting" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'match_high_price'">
                <el-form-item label="源目录">
                  <el-input v-model="step.config.source_dir" placeholder="百日新高" />
                </el-form-item>
                <el-form-item label="上传匹配数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="info">目标目录: {{ getTargetDirDisplay('match_high_price') }}</el-tag>
                    </div>
                    <div class="upload-actions">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        :id="`file-input-${index}`"
                        @change="handleFileUpload($event, step, index)"
                        style="display: none"
                      />
                      <el-button
                        type="primary"
                        size="small"
                        @click="triggerFileInput(index)"
                        :loading="uploadingSteps.has(`step_${index}`)"
                      >
                        <el-icon><Upload /></el-icon>
                        上传Excel文件
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="已上传文件" v-if="step.type === 'match_high_price'">
                  <div class="uploaded-files-list" v-if="uploadedFiles[`step_${index}`]?.length > 0">
                    <div v-for="file in uploadedFiles[`step_${index}`]" :key="file.path" class="file-item">
                      <div class="file-info">
                        <el-icon><Document /></el-icon>
                        <span class="file-name">{{ file.filename }}</span>
                        <span class="file-size">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <div class="file-actions">
                        <el-button size="small" link @click="previewFile(file.path)">
                          <el-icon><View /></el-icon>
                        </el-button>
                        <el-button size="small" link type="danger" @click="deleteUploadedFile(file.path, step, index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="新增列名">
                  <el-input v-model="step.config.new_column_name" placeholder="百日新高" />
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="output_2.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'match_ma20'">
                <el-form-item label="源目录">
                  <el-input v-model="step.config.source_dir" placeholder="20日均线" />
                </el-form-item>
                <el-form-item label="上传匹配数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="info">目标目录: {{ getTargetDirDisplay('match_ma20') }}</el-tag>
                    </div>
                    <div class="upload-actions">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        :id="`file-input-${index}`"
                        @change="handleFileUpload($event, step, index)"
                        style="display: none"
                      />
                      <el-button
                        type="primary"
                        size="small"
                        @click="triggerFileInput(index)"
                        :loading="uploadingSteps.has(`step_${index}`)"
                      >
                        <el-icon><Upload /></el-icon>
                        上传Excel文件
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="已上传文件" v-if="step.type === 'match_ma20'">
                  <div class="uploaded-files-list" v-if="uploadedFiles[`step_${index}`]?.length > 0">
                    <div v-for="file in uploadedFiles[`step_${index}`]" :key="file.path" class="file-item">
                      <div class="file-info">
                        <el-icon><Document /></el-icon>
                        <span class="file-name">{{ file.filename }}</span>
                        <span class="file-size">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <div class="file-actions">
                        <el-button size="small" link @click="previewFile(file.path)">
                          <el-icon><View /></el-icon>
                        </el-button>
                        <el-button size="small" link type="danger" @click="deleteUploadedFile(file.path, step, index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="新增列名">
                  <el-input v-model="step.config.new_column_name" placeholder="20日均线" />
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="output_4.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'match_soe'">
                <el-form-item label="源目录">
                  <el-input v-model="step.config.source_dir" placeholder="国企" />
                </el-form-item>
                <el-form-item label="上传匹配数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="info">目标目录: {{ getTargetDirDisplay('match_soe') }}</el-tag>
                    </div>
                    <div class="upload-actions">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        :id="`file-input-${index}`"
                        @change="handleFileUpload($event, step, index)"
                        style="display: none"
                      />
                      <el-button
                        type="primary"
                        size="small"
                        @click="triggerFileInput(index)"
                        :loading="uploadingSteps.has(`step_${index}`)"
                      >
                        <el-icon><Upload /></el-icon>
                        上传Excel文件
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="已上传文件" v-if="step.type === 'match_soe'">
                  <div class="uploaded-files-list" v-if="uploadedFiles[`step_${index}`]?.length > 0">
                    <div v-for="file in uploadedFiles[`step_${index}`]" :key="file.path" class="file-item">
                      <div class="file-info">
                        <el-icon><Document /></el-icon>
                        <span class="file-name">{{ file.filename }}</span>
                        <span class="file-size">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <div class="file-actions">
                        <el-button size="small" link @click="previewFile(file.path)">
                          <el-icon><View /></el-icon>
                        </el-button>
                        <el-button size="small" link type="danger" @click="deleteUploadedFile(file.path, step, index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="新增列名">
                  <el-input v-model="step.config.new_column_name" placeholder="国企" />
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="output_5.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'match_sector'">
                <el-form-item label="源目录">
                  <el-input v-model="step.config.source_dir" placeholder="一级板块" />
                </el-form-item>
                <el-form-item label="上传匹配数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="info">目标目录: {{ getTargetDirDisplay('match_sector') }}</el-tag>
                    </div>
                    <div class="upload-actions">
                      <input
                        type="file"
                        accept=".xlsx,.xls"
                        :id="`file-input-${index}`"
                        @change="handleFileUpload($event, step, index)"
                        style="display: none"
                      />
                      <el-button
                        type="primary"
                        size="small"
                        @click="triggerFileInput(index)"
                        :loading="uploadingSteps.has(`step_${index}`)"
                      >
                        <el-icon><Upload /></el-icon>
                        上传Excel文件
                      </el-button>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="已上传文件" v-if="step.type === 'match_sector'">
                  <div class="uploaded-files-list" v-if="uploadedFiles[`step_${index}`]?.length > 0">
                    <div v-for="file in uploadedFiles[`step_${index}`]" :key="file.path" class="file-item">
                      <div class="file-info">
                        <el-icon><Document /></el-icon>
                        <span class="file-name">{{ file.filename }}</span>
                        <span class="file-size">{{ formatFileSize(file.size) }}</span>
                      </div>
                      <div class="file-actions">
                        <el-button size="small" link @click="previewFile(file.path)">
                          <el-icon><View /></el-icon>
                        </el-button>
                        <el-button size="small" link type="danger" @click="deleteUploadedFile(file.path, step, index)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="新增列名">
                  <el-input v-model="step.config.new_column_name" placeholder="一级板块" />
                </el-form-item>
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="并购重组日期.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'condition_intersection'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                    @change="onIntersectionDateChange(step)"
                  />
                </el-form-item>

                <el-form-item label="过滤条件">
                  <div style="width: 100%">
                    <div style="display: flex; align-items: center; margin-bottom: 8px;">
                      <span style="margin-right: 12px; font-size: 13px; color: #606266;">条件逻辑:</span>
                      <el-radio-group v-model="step.config.filter_logic" size="small">
                        <el-radio-button label="AND">AND（全部满足）</el-radio-button>
                        <el-radio-button label="OR">OR（满足任一）</el-radio-button>
                      </el-radio-group>
                    </div>
                    <div v-for="(filter, fIdx) in step.config.filter_conditions" :key="fIdx" style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                      <el-checkbox v-model="filter.enabled">{{ filter.column }}</el-checkbox>
                      <el-button link type="danger" size="small" @click="removeFilter(step, fIdx)" :disabled="step.config.filter_conditions.length <= 1">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                    <el-button size="small" @click="addFilter(step)" :disabled="getAvailableFilters(step).length === 0">
                      <el-icon><Plus /></el-icon>
                      添加过滤条件
                    </el-button>
                  </div>
                </el-form-item>

                <el-form-item label="工作流顺序">
                  <div style="width: 100%">
                    <div
                      v-for="(wtype, tIdx) in step.config.type_order"
                      :key="wtype"
                      style="display: flex; align-items: center; gap: 8px; padding: 6px 12px; margin-bottom: 4px; background: #f5f7fa; border-radius: 4px;"
                    >
                      <span style="color: #909399; cursor: grab;">≡</span>
                      <span style="flex: 1;">{{ tIdx + 1 }}. {{ wtype }}</span>
                      <el-button link size="small" :disabled="tIdx === 0" @click="moveTypeOrder(step, tIdx, -1)">↑</el-button>
                      <el-button link size="small" :disabled="tIdx === step.config.type_order.length - 1" @click="moveTypeOrder(step, tIdx, 1)">↓</el-button>
                    </div>
                  </div>
                </el-form-item>

                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="7条件交集{date}.xlsx" />
                </el-form-item>

                <el-form-item label="标注百日新高周期">
                  <div style="width: 100%">
                    <div style="font-size: 12px; color: #909399; margin-bottom: 6px;">
                      为每个周期生成 2 个输出列："YYYY-MM-DD至YYYY-MM-DD期间百日新高次数" 和 "…期间百日新高的日期"。对比历史选股池里该股票的数据日期。
                    </div>
                    <div v-for="(p, pIdx) in (step.config.high_price_periods || [])" :key="pIdx"
                         style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                      <span style="color: #909399; width: 16px;">{{ pIdx + 1 }}.</span>
                      <el-date-picker
                        v-model="p.start"
                        type="date"
                        placeholder="开始日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        style="width: 160px"
                      />
                      <span>~</span>
                      <el-date-picker
                        v-model="p.end"
                        type="date"
                        placeholder="结束日期"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        style="width: 160px"
                      />
                      <el-button link type="danger" size="small" @click="removeHighPricePeriod(step, pIdx)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </div>
                    <el-button size="small" @click="addHighPricePeriod(step)">
                      <el-icon><Plus /></el-icon>
                      添加周期
                    </el-button>
                  </div>
                </el-form-item>
              </template>

              <template v-if="step.type === 'pledge_trend_analysis'">
                <el-form-item label="趋势算法">
                  <el-select v-model="step.config.trend_algo" style="width: 100%">
                    <el-option label="Mann-Kendall（默认，推荐）" value="mann_kendall" />
                    <el-option label="月度下采样" value="monthly_downsample" />
                    <el-option label="线性回归" value="linear_regression" />
                  </el-select>
                </el-form-item>

                <el-form-item
                  v-if="step.config.trend_algo === 'mann_kendall'"
                  label="MK 显著性水平 p (0~1)"
                >
                  <el-input-number
                    v-model="step.config.mk_pvalue"
                    :min="0.001" :max="0.2" :step="0.01"
                    :precision="3" style="width: 200px"
                  />
                  <span class="param-hint">&nbsp; 概率值(无量纲)；p &lt; 阈值 判为趋势显著，0.05 ≈ 95% 置信度</span>
                </el-form-item>

                <el-form-item
                  v-if="step.config.trend_algo === 'monthly_downsample'"
                  label="月度最大反转数"
                >
                  <el-input-number
                    v-model="step.config.b_max_reversals"
                    :min="0" :max="12" :step="1" style="width: 200px"
                  />
                  <span class="param-hint">&nbsp; ≤ 阈值 判为单向趋势</span>
                </el-form-item>

                <el-form-item
                  v-if="step.config.trend_algo === 'linear_regression'"
                  label="线性回归最小 R²"
                >
                  <el-input-number
                    v-model="step.config.c_min_r2"
                    :min="0.1" :max="0.99" :step="0.05"
                    :precision="2" style="width: 200px"
                  />
                  <span class="param-hint">&nbsp; ≥ 阈值 判为趋势显著</span>
                </el-form-item>

                <el-form-item label="异动无变化 |Δ| < X 百分点">
                  <el-input-number
                    v-model="step.config.event_no_change_threshold"
                    :min="0" :max="5" :step="0.1"
                    :precision="1" style="width: 200px"
                  />
                  <span class="param-hint">
                    &nbsp; Δ = 当日累计质押比例 − 前次累计质押比例（单位：百分点 pct）；
                    |Δ| &lt; 阈值 判"本次质押趋势无变化"
                  </span>
                </el-form-item>

                <el-form-item label="异动大幅 |Δ| ≥ X 百分点">
                  <el-input-number
                    v-model="step.config.event_large_threshold"
                    :min="0.5" :max="20" :step="0.5"
                    :precision="1" style="width: 200px"
                  />
                  <span class="param-hint">
                    &nbsp; |Δ| ≥ 阈值 判"大幅激增/大幅骤减"；介于两阈值之间判"小幅转增/转减"
                  </span>
                </el-form-item>

                <el-form-item label="历史窗口 (天)">
                  <el-input-number
                    v-model="step.config.window_days"
                    :min="30" :max="1500" :step="30" style="width: 200px"
                  />
                  <span class="param-hint">&nbsp; 单股历史质押记录窗口</span>
                </el-form-item>

                <el-form-item label="行有效期 (天)">
                  <el-input-number
                    v-model="step.config.row_recency_days"
                    :min="1" :max="365" :step="1" style="width: 200px"
                  />
                  <span class="param-hint">&nbsp; 只处理最新公告日在此范围内的行</span>
                </el-form-item>

                <el-form-item label="输出文件名">
                  <el-input
                    v-model="step.config.output_filename"
                    placeholder="默认使用 match_sector 的输出文件名（5质押{date}.xlsx）"
                  />
                </el-form-item>
              </template>

              <template v-if="step.type === 'export_ma20_trend'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                    @change="onTrendDateStrChange(step)"
                  />
                </el-form-item>

                <el-form-item label="趋势时间范围">
                  <div style="width: 100%">
                    <div style="display: flex; gap: 8px; margin-bottom: 8px;">
                      <el-radio-group v-model="step.config.date_preset" size="small" @change="onTrendPresetChange(step)">
                        <el-radio-button label="1m">最近1个月</el-radio-button>
                        <el-radio-button label="6m">最近半年</el-radio-button>
                        <el-radio-button label="1y">最近1年</el-radio-button>
                        <el-radio-button label="custom">自定义</el-radio-button>
                      </el-radio-group>
                    </div>
                    <el-date-picker
                      v-if="step.config.date_preset === 'custom'"
                      v-model="step.config.date_range"
                      type="daterange"
                      range-separator="至"
                      start-placeholder="开始日期"
                      end-placeholder="结束日期"
                      format="YYYY-MM-DD"
                      value-format="YYYY-MM-DD"
                      style="width: 100%"
                      @change="onTrendRangeChange(step)"
                    />
                    <el-tag v-else type="info" style="margin-top: 4px;">
                      {{ step.config.date_range_start || '?' }} 至 {{ step.config.date_range_end || '?' }}
                    </el-tag>
                  </div>
                </el-form-item>

                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="10站上20日均线趋势.xlsx" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'ranking_sort'">
                <el-form-item label="数据日期">
                  <el-date-picker
                    v-model="step.config.date_str"
                    type="date"
                    placeholder="选择数据日期"
                    format="YYYY-MM-DD"
                    value-format="YYYY-MM-DD"
                    style="width: 200px"
                  />
                </el-form-item>
                <el-alert
                  title="自动使用第2列降序排列，Top5深红标注，排名提升浅红标注"
                  type="info"
                  :closable="false"
                  style="margin-bottom: 12px"
                />
                <el-form-item label="输出文件名">
                  <el-input v-model="step.config.output_filename" placeholder="8涨幅排名0201-{date}.xlsx (留空自动生成)" />
                </el-form-item>
              </template>

              <template v-if="step.type === 'pending'">
                <el-alert title="此步骤暂未配置，待后续开发" type="info" :closable="false" />
              </template>
            </el-card>
          </div>
        </div>

        <el-form-item v-if="!isAggregationType && form.workflow_type !== '涨幅排名'">>
          <el-button @click="addStep">
            <el-icon><Plus /></el-icon>
            添加步骤
          </el-button>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showStepsDialog" title="工作流步骤详情" width="700px">
      <el-timeline>
        <el-timeline-item
          v-for="(step, index) in currentWorkflow?.steps"
          :key="index"
          :timestamp="'步骤 ' + (index + 1)"
          :type="getTimelineType(step.status)"
          placement="top"
        >
          <el-card>
            <h4>{{ getStepTypeName(step.type) }}</h4>
            <p><strong>类型:</strong> {{ step.type }}</p>
            <template v-if="step.config">
              <p v-if="step.config.data_source_id"><strong>数据源ID:</strong> {{ step.config.data_source_id }}</p>
              <p v-if="step.config.file_path"><strong>文件路径:</strong> {{ step.config.file_path }}</p>
              <p v-if="step.config.columns"><strong>保留列:</strong> {{ step.config.columns.join(', ') }}</p>
              <p v-if="step.config.output_filename"><strong>输出文件:</strong> {{ step.config.output_filename }}</p>
            </template>
            <p><strong>状态:</strong> <el-tag size="small" :type="getStepStatusType(step.status)">{{ step.status || '未执行' }}</el-tag></p>
          </el-card>
        </el-timeline-item>
      </el-timeline>
    </el-dialog>

    <el-dialog v-model="showExecuteDialog" title="工作流执行" width="700px" @close="onExecuteDialogClose">
      <el-form label-width="120px">
        <el-form-item label="工作流名称">
          <span>{{ currentWorkflow?.name }}</span>
        </el-form-item>
        <el-form-item label="执行耗时" v-if="executionStartTime">
          <el-tag type="warning" size="large">
            <el-icon><Timer /></el-icon>
            {{ executionTime }}
          </el-tag>
        </el-form-item>
        <el-form-item label="执行步骤">
          <el-steps :active="executionStep" direction="vertical">
            <el-step
              v-for="(step, index) in currentWorkflow?.steps"
              :key="index"
              :title="getStepTypeName(step.type)"
              :status="getStepStatus(step.status)"
            />
          </el-steps>
        </el-form-item>
        <el-form-item label="当前步骤" v-if="executing">
          <el-tag type="primary" size="large">{{ getStepTypeName(currentWorkflow?.steps[executionStep]?.type) }}</el-tag>
        </el-form-item>
        <el-form-item label="执行结果" v-if="executionResult">
          <el-alert :type="executionResult.type" :title="executionResult.message" show-icon />
        </el-form-item>

        <el-form-item label="质押趋势" v-if="executionResult?.stats && executionResult?.stats?.by_source">
          <div class="pledge-summary-card">
            <div class="pledge-row">
              <el-tag type="info" v-if="executionResult.stats.input_total != null">
                输入 {{ executionResult.stats.input_total }}
              </el-tag>
              <el-tag>实际查询 {{ executionResult.stats.total }}</el-tag>
              <el-tag type="success">成功 {{ executionResult.stats.ok }}</el-tag>
              <el-tag type="warning">无历史 {{ executionResult.stats.empty }}</el-tag>
              <el-tag type="danger" v-if="executionResult.stats.fail > 0">失败 {{ executionResult.stats.fail }}</el-tag>
              <el-tag type="info" v-if="executionResult.stats.skipped_preset > 0">跳过(已有值) {{ executionResult.stats.skipped_preset }}</el-tag>
              <el-tag type="info" v-if="executionResult.stats.skipped_old > 0">跳过(过期) {{ executionResult.stats.skipped_old }}</el-tag>
            </div>
            <div class="pledge-row pledge-row-stats">
              <span class="pledge-label">数据源:</span>
              <span class="pledge-stat">东财 <b>{{ executionResult.stats.by_source.eastmoney }}</b></span>
              <span class="pledge-stat">缓存 <b>{{ executionResult.stats.by_source.cache }}</b></span>
              <span class="pledge-stat">降级 AkShare <b>{{ executionResult.stats.by_source.akshare }}</b></span>
              <span class="pledge-stat">空 <b>{{ executionResult.stats.by_source.empty }}</b></span>
            </div>
            <div class="pledge-row pledge-row-stats" v-if="executionResult.stats.by_result">
              <span class="pledge-label">趋势判定:</span>
              <span class="pledge-stat">持续递增 <b>{{ executionResult.stats.by_result['持续递增'] || 0 }}</b></span>
              <span class="pledge-stat">持续递减 <b>{{ executionResult.stats.by_result['持续递减'] || 0 }}</b></span>
              <span class="pledge-stat">无趋势 <b>{{ executionResult.stats.by_result['无趋势'] || 0 }}</b></span>
            </div>
            <div class="pledge-row pledge-row-stats" v-if="executionResult.stats.by_result">
              <span class="pledge-label">异动分类:</span>
              <span class="pledge-stat">小幅转增 <b>{{ executionResult.stats.by_result['小幅转增'] || 0 }}</b></span>
              <span class="pledge-stat">大幅激增 <b>{{ executionResult.stats.by_result['大幅激增'] || 0 }}</b></span>
              <span class="pledge-stat">小幅转减 <b>{{ executionResult.stats.by_result['小幅转减'] || 0 }}</b></span>
              <span class="pledge-stat">大幅骤减 <b>{{ executionResult.stats.by_result['大幅骤减'] || 0 }}</b></span>
              <span class="pledge-stat">无变化 <b>{{ executionResult.stats.by_result['本次质押趋势无变化'] || 0 }}</b></span>
              <span class="pledge-stat">空 <b>{{ executionResult.stats.by_result['空'] || 0 }}</b></span>
            </div>
            <el-collapse v-if="executionResult.fail_samples?.length" style="margin-top:8px;">
              <el-collapse-item :title="`失败样本 (${executionResult.fail_samples.length})`" name="fail">
                <div v-for="(s, i) in executionResult.fail_samples" :key="i" class="fail-sample">
                  <strong>{{ s.symbol }}</strong>: {{ s.error }}
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-form-item>

        <el-form-item label="警告" v-if="executionResult?.warnings?.length">
          <el-alert
            v-for="(w, i) in executionResult.warnings"
            :key="i"
            type="warning"
            :title="w"
            show-icon
            :closable="false"
            style="margin-bottom:4px;"
          />
        </el-form-item>
        <template v-if="executionComplete && resultData.length">
          <el-form-item label="过滤结果">
            <span>{{ filteredResultData.length }} 条 / {{ resultData.length }} 条</span>
          </el-form-item>
          <el-table :data="filteredResultData" border max-height="400" size="small">
            <el-table-column v-for="col in resultColumns" :key="col" :prop="col" :label="col" width="130" show-overflow-tooltip />
          </el-table>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showExecuteDialog = false" v-if="!executing">关闭</el-button>
        <el-button type="primary" @click="startExecution" v-if="!executing && !executionComplete">开始执行</el-button>
        <el-button type="success" @click="downloadResult" v-if="executionComplete && executionResult?.file_path">
          <el-icon><Download /></el-icon>
          下载结果
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="previewDialogVisible" title="文件预览" width="800px">
      <div v-if="previewData.filename">
        <el-alert :title="`${previewData.filename} (共 ${previewData.total_rows} 行)`" type="info" :closable="false" />
        <el-table :data="previewData.preview" border max-height="400" size="small" style="margin-top: 15px">
          <el-table-column v-for="col in previewData.columns" :key="col" :prop="col" :label="col" width="130" show-overflow-tooltip />
        </el-table>
      </div>
    </el-dialog>

    <el-drawer v-model="batchProgressDrawer" title="并行执行进度" direction="rtl" size="450px" :close-on-press-escape="true" @close="onBatchDrawerClose">
      <div class="batch-progress-container">
        <div class="batch-overview">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="状态">
              <el-tag :type="batchStatusTagType(batchStatus.status)" size="small">{{ batchStatusText(batchStatus.status) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="总数">{{ batchStatus.total || 0 }}</el-descriptions-item>
            <el-descriptions-item label="已完成">
              <el-tag type="success" size="small">{{ batchStatus.completed || 0 }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="失败">
              <el-tag type="danger" size="small">{{ batchStatus.failed || 0 }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">
              <span :style="{ color: batchExecuting ? '#E6A23C' : '#67C23A', fontWeight: 'bold' }">
                {{ formatElapsed(batchElapsedSeconds) }}
              </span>
            </el-descriptions-item>
          </el-descriptions>
          <el-progress
            v-if="batchStatus.total"
            :percentage="Math.round(((batchStatus.completed || 0) + (batchStatus.failed || 0)) / batchStatus.total * 100)"
            :status="batchProgressStatus"
            :stroke-width="18"
            style="margin-top: 15px"
          >
            <span>{{ (batchStatus.completed || 0) + (batchStatus.failed || 0) }} / {{ batchStatus.total }}</span>
          </el-progress>
        </div>

        <el-divider content-position="left">各工作流执行详情</el-divider>

        <div class="batch-results-list">
          <div v-for="(result, idx) in (batchStatus.results || [])" :key="idx" class="batch-result-item">
            <div class="result-header">
              <el-tag :type="result.status === 'completed' ? 'success' : result.status === 'failed' ? 'danger' : 'primary'" size="small">
                {{ getWorkflowName(result.workflow_id) }}
              </el-tag>
              <el-tag :type="result.status === 'completed' ? 'success' : result.status === 'failed' ? 'danger' : 'primary'" size="small" effect="plain">
                {{ batchStatusText(result.status) }}
              </el-tag>
              <el-text v-if="result.duration" type="info" size="small" style="margin-left: 6px">{{ result.duration }}s</el-text>
              <el-button
                v-if="result.status === 'completed'"
                type="primary"
                size="small"
                text
                @click="downloadBatchResult(result.workflow_id)"
                style="margin-left: auto"
              >
                <el-icon><Download /></el-icon> 下载
              </el-button>
            </div>
            <div v-if="result.error" class="result-error">
              <el-text type="danger" size="small">{{ result.error }}</el-text>
            </div>
            <div v-if="result.output_file" class="result-output">
              <el-text type="info" size="small">输出: {{ result.output_file.split('/').pop() }}</el-text>
            </div>
          </div>
          <el-empty v-if="!batchStatus.results?.length && batchStatus.status === 'running'" description="正在执行中..." :image-size="60" />
        </div>

        <div class="batch-actions" v-if="['completed', 'partial', 'failed', 'cancelled'].includes(batchStatus.status)">
          <el-button type="primary" @click="batchProgressDrawer = false">关闭</el-button>
          <el-button @click="fetchWorkflows">刷新列表</el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Timer, FolderOpened, Upload, Delete, View, Download, Document, Promotion, Plus } from '@element-plus/icons-vue'

const formatBeijingTime = (dateStr) => {
  if (!dateStr) return '-'
  const d = new Date(dateStr.endsWith('Z') ? dateStr : dateStr + 'Z')
  const bj = new Date(d.getTime() + 8 * 3600000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${bj.getUTCFullYear()}-${pad(bj.getUTCMonth() + 1)}-${pad(bj.getUTCDate())} ${pad(bj.getUTCHours())}:${pad(bj.getUTCMinutes())}:${pad(bj.getUTCSeconds())}`
}

const loading = ref(false)
const showDialog = ref(false)
const showStepsDialog = ref(false)
const showExecuteDialog = ref(false)
const executing = ref(false)
const executionComplete = ref(false)
const hasDownloaded = ref(false)
const executionStep = ref(0)
const executionResult = ref(null)
const resultData = ref([])
const resultColumns = ref([])
const workflows = ref([])
const dataSources = ref([])
const workflowTypes = ref([])
const currentWorkflow = ref(null)
const isEditing = ref(false)
const editingId = ref(null)
const fileInputRefs = ref([])
const executionStartTime = ref(null)
const executionTimer = ref(null)
const executionTime = ref('00:00:00')

const uploadedFiles = ref({})
const publicFiles = ref({})
const uploadingSteps = ref(new Set())
const previewDialogVisible = ref(false)
const previewData = ref({})
const editingStepIndex = ref(null)

const selectedWorkflows = ref([])
const batchExecuting = ref(false)
const batchProgressDrawer = ref(false)
const batchStatus = ref({})
const batchPollingTimer = ref(null)
const batchElapsedSeconds = ref(0)
const batchTimerInterval = ref(null)
const workflowTableRef = ref(null)
const pendingTimeouts = ref([])
const executionAbortController = ref(null)
const highlightedWorkflowId = ref(null)
const highlightTimer = ref(null)

const applyHighlightDOM = (id) => {
  const tableEl = workflowTableRef.value?.$el
  if (!tableEl) return
  // 清除旧高亮
  clearHighlightDOM()
  const rows = tableEl.querySelectorAll('.el-table__body-wrapper tbody tr')
  const idx = workflows.value.findIndex(w => w.id === id)
  if (idx >= 0 && rows[idx]) {
    const row = rows[idx]
    const cells = row.querySelectorAll('td')
    cells.forEach(td => {
      td.style.transition = 'background-color 0.5s ease'
      td.style.backgroundColor = 'rgba(103, 194, 58, 0.35)'
    })
    row.scrollIntoView({ behavior: 'smooth', block: 'center' })
    // 闪烁 3 次后淡出
    let count = 0
    const blink = () => {
      count++
      const on = count % 2 === 0
      cells.forEach(td => {
        td.style.backgroundColor = on ? 'rgba(103, 194, 58, 0.35)' : ''
      })
      if (count < 6) {
        setTimeout(blink, 400)
      } else {
        cells.forEach(td => { td.style.transition = ''; td.style.backgroundColor = '' })
      }
    }
    setTimeout(blink, 400)
  }
}

const clearHighlightDOM = () => {
  const tableEl = workflowTableRef.value?.$el
  if (!tableEl) return
  tableEl.querySelectorAll('.el-table__body-wrapper tbody tr td').forEach(td => {
    td.style.transition = ''
    td.style.backgroundColor = ''
  })
}

const highlightWorkflow = (id) => {
  if (highlightTimer.value) clearTimeout(highlightTimer.value)
  highlightedWorkflowId.value = id
  nextTick(() => applyHighlightDOM(id))
  highlightTimer.value = setTimeout(() => {
    highlightedWorkflowId.value = null
    highlightTimer.value = null
  }, 3000)
}

const getRowClassName = ({ row }) => {
  return row.id === highlightedWorkflowId.value ? 'highlight-row' : ''
}

const openOutputDirectory = async () => {
  const basePath = '/app/data/excel'
  let datePath = basePath
  if (executionResult.value?.file_path) {
    const match = executionResult.value.file_path.match(/(\d{4}-\d{2}-\d{2})/)
    if (match) {
      datePath = `${basePath}/${match[1]}`
    }
  }
  try {
    await api.post('/workflows/open-directory', { path: datePath })
    ElMessage.success('已打开目录')
  } catch (error) {
    ElMessage.error('打开目录失败')
  }
}

const filteredResultData = computed(() => {
  return resultData.value
})

const updateExecutionTime = () => {
  if (executionStartTime.value) {
    const elapsed = Math.floor((Date.now() - executionStartTime.value) / 1000)
    const hours = Math.floor(elapsed / 3600)
    const minutes = Math.floor((elapsed % 3600) / 60)
    const seconds = elapsed % 60
    executionTime.value = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
}

const getDateStr = (stepIndex = 0) => {
  if (currentWorkflow.value?.steps?.[stepIndex]?.config?.date_str) {
    return currentWorkflow.value.steps[stepIndex].config.date_str
  }
  return new Date().toISOString().split('T')[0]
}

const defaultStep = () => ({
  type: 'merge_excel',
  config: {
    date_str: new Date().toISOString().split('T')[0],
    data_source_id: null,
    file_path: '',
    columns: [],
    output_filename: 'output_1.xlsx',
    apply_formatting: true,
    stock_code_column: '',
    date_column: '',
    use_fixed_columns: true,
    exclude_patterns_text: 'total_,output_',
    exclude_patterns: ['total_', 'output_'],
    source_dir: '百日新高',
    new_column_name: '百日新高'
  },
  status: 'pending'
})

const form = ref({
  name: '',
  description: '',
  workflow_type: '',
  steps: [defaultStep()]
})

const getStatusType = (status) => {
  const types = {
    active: 'success',
    inactive: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const getStepType = (type) => {
  const types = {
    import_excel: 'primary',
    merge_excel: 'primary',
    dedup: 'success',
    smart_dedup: 'success',
    extract_columns: 'warning',
    export_excel: 'info',
    condition_intersection: 'warning',
    export_ma20_trend: 'warning',
    ranking_sort: 'success',
    pledge_trend_analysis: 'warning',
    pending: 'danger'
  }
  return types[type] || 'info'
}

const getStepTypeName = (type) => {
  const names = {
    import_excel: '导入Excel',
    merge_excel: '合并当日数据源',
    dedup: '去除重复行',
    smart_dedup: '智能去重',
    extract_columns: '提取列',
    export_excel: '导出Excel',
    match_high_price: '匹配百日新高',
    match_ma20: '匹配20日均线',
    match_soe: '匹配国企',
    match_sector: '匹配一级板块',
    condition_intersection: '合并当日数据',
    export_ma20_trend: '导出趋势Excel',
    ranking_sort: '涨幅排名排序',
    pledge_trend_analysis: '质押异动和趋势',
    pending: '待定'
  }
  return names[type] || type
}

// 条件交集 & 导出20日均线趋势 相关
const AGGREGATION_TYPES = ['条件交集', '导出20日均线趋势']
const isAggregationType = computed(() => AGGREGATION_TYPES.includes(form.value.workflow_type))

const FILTER_COLUMNS = ['百日新高', '20日均线', '国企', '一级板块']
const DEFAULT_TYPE_ORDER = ['并购重组', '股权转让', '增发实现', '申报并购重组', '减持叠加质押和大宗交易', '质押', '招投标']

const defaultIntersectionStep = () => {
  const today = new Date().toISOString().split('T')[0]
  return {
    type: 'condition_intersection',
    config: {
      date_str: today,
      filter_conditions: [{ column: '百日新高', enabled: true }],
      filter_logic: 'AND',
      type_order: [...DEFAULT_TYPE_ORDER],
      output_filename: `7条件交集${today.replace(/-/g, '')}.xlsx`,
      high_price_periods: [{ start: '2026-03-18', end: today }]
    },
    status: 'pending'
  }
}

const defaultRankingSteps = () => {
  const today = new Date().toISOString().split('T')[0]
  return [
    {
      type: 'merge_excel',
      config: {
        date_str: today,
        output_filename: 'total_1.xlsx',
        exclude_patterns_text: 'total_,output_,8涨幅排名',
        exclude_patterns: ['total_', 'output_', '8涨幅排名'],
        apply_formatting: true,
      },
      status: 'pending'
    },
    {
      type: 'ranking_sort',
      config: {
        date_str: today,
        output_filename: '',
      },
      status: 'pending'
    }
  ]
}

const computeTrendDateRange = (preset, anchorDateStr) => {
  const anchor = anchorDateStr ? new Date(anchorDateStr) : new Date()
  if (isNaN(anchor.getTime())) {
    return { start: '', end: '' }
  }
  let start
  if (preset === '1m') {
    start = new Date(anchor.getFullYear(), anchor.getMonth() - 1, anchor.getDate())
  } else if (preset === '6m') {
    start = new Date(anchor.getFullYear(), anchor.getMonth() - 6, anchor.getDate())
  } else if (preset === '1y') {
    start = new Date(anchor.getFullYear() - 1, anchor.getMonth(), anchor.getDate())
  } else {
    return { start: '', end: '' }
  }
  const fmt = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }
  return { start: fmt(start), end: fmt(anchor) }
}

const defaultMa20TrendStep = () => {
  const today = new Date().toISOString().split('T')[0]
  const range = computeTrendDateRange('6m', today)
  return {
    type: 'export_ma20_trend',
    config: {
      date_str: today,
      date_preset: '6m',
      date_range_start: range.start,
      date_range_end: range.end,
      date_range: null,
      output_filename: '10站上20日均线趋势.xlsx'
    },
    status: 'pending'
  }
}

const onTrendPresetChange = (step) => {
  if (step.config.date_preset !== 'custom') {
    const range = computeTrendDateRange(step.config.date_preset, step.config.date_str)
    step.config.date_range_start = range.start
    step.config.date_range_end = range.end
    step.config.date_range = null
  }
}

const onTrendDateStrChange = (step) => {
  if (step.config.date_preset && step.config.date_preset !== 'custom') {
    const range = computeTrendDateRange(step.config.date_preset, step.config.date_str)
    step.config.date_range_start = range.start
    step.config.date_range_end = range.end
    step.config.date_range = null
  }
}

const onTrendRangeChange = (step) => {
  if (step.config.date_range && step.config.date_range.length === 2) {
    step.config.date_range_start = step.config.date_range[0]
    step.config.date_range_end = step.config.date_range[1]
  }
}

const getAvailableFilters = (step) => {
  const used = new Set((step.config.filter_conditions || []).map(f => f.column))
  return FILTER_COLUMNS.filter(c => !used.has(c))
}

const addFilter = (step) => {
  const available = getAvailableFilters(step)
  if (available.length > 0) {
    step.config.filter_conditions.push({ column: available[0], enabled: true })
  }
}

const removeFilter = (step, idx) => {
  step.config.filter_conditions.splice(idx, 1)
}

const moveTypeOrder = (step, idx, direction) => {
  const arr = step.config.type_order
  const newIdx = idx + direction
  if (newIdx < 0 || newIdx >= arr.length) return
  const temp = arr[idx]
  arr[idx] = arr[newIdx]
  arr[newIdx] = temp
}

const addHighPricePeriod = (step) => {
  if (!step.config.high_price_periods) step.config.high_price_periods = []
  const today = step.config.date_str || new Date().toISOString().split('T')[0]
  step.config.high_price_periods.push({ start: '2026-03-18', end: today })
}

const removeHighPricePeriod = (step, idx) => {
  step.config.high_price_periods.splice(idx, 1)
}

const onIntersectionDateChange = (step) => {
  const date = step.config.date_str || new Date().toISOString().split('T')[0]
  step.config.output_filename = `7条件交集${date.replace(/-/g, '')}.xlsx`
  // 只有 1 条周期时自动同步 end 到数据日期
  const periods = step.config.high_price_periods || []
  if (periods.length === 1) {
    periods[0].end = date
  }
}

const onMergeDateChange = (step, index) => {
  fetchUploadedFiles(step, index)
  // 涨幅排名: 步骤1日期联动步骤2 + 刷新公共文件列表
  if (form.value.workflow_type === '涨幅排名') {
    const newDate = step.config.date_str
    form.value.steps.forEach((s, i) => {
      if (i !== index && s.config) {
        s.config.date_str = newDate
      }
    })
    // 刷新步骤1的公共文件列表（date-aware）
    fetchPublicFiles(step, index)
  }
}

// 标记是否正在加载编辑数据（跳过 watcher 副作用）
const loadingEditData = ref(false)

// 监听 workflow_type 变化，自动切换步骤（仅在用户手动切换类型时生效）
watch(() => form.value.workflow_type, (newType, oldType) => {
  if (loadingEditData.value) return
  const wasAgg = AGGREGATION_TYPES.includes(oldType)
  const isAgg = AGGREGATION_TYPES.includes(newType)
  if (newType === '条件交集') {
    form.value.steps = [defaultIntersectionStep()]
  } else if (newType === '导出20日均线趋势') {
    form.value.steps = [defaultMa20TrendStep()]
  } else if (newType === '涨幅排名') {
    form.value.steps = defaultRankingSteps()
  } else if ((wasAgg || oldType === '涨幅排名') && !isAgg && newType !== '涨幅排名') {
    form.value.steps = [defaultStep()]
  }
})

const getTimelineType = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  return 'info'
}

const getStepStatusType = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'primary'
  if (status === 'failed') return 'danger'
  return 'info'
}

const getStepStatus = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'running') return 'process'
  if (status === 'failed') return 'error'
  return 'wait'
}

const openCreateDialog = () => {
  isEditing.value = false
  editingId.value = null
  uploadedFiles.value = {}
  publicFiles.value = {}
  form.value = {
    name: '',
    description: '',
    workflow_type: '',
    steps: [defaultStep()]
  }
  showDialog.value = true
}

const addStep = () => {
  const newStep = defaultStep()
  if (newStep.type === 'match_sector') {
    const firstStepDate = form.value.steps[0]?.config?.date_str || new Date().toISOString().split('T')[0]
    newStep.config.output_filename = getDefaultFinalFilename(firstStepDate)
  }
  form.value.steps.push(newStep)
}

const removeStep = (index) => {
  form.value.steps.splice(index, 1)
}

// 按工作流类型生成 match_sector 默认输出文件名（与后端 output_template 保持一致）
const getDefaultFinalFilename = (dateStr) => {
  const d = (dateStr || new Date().toISOString().split('T')[0]).replace(/-/g, '')
  const wt = form.value.workflow_type || ''
  const map = {
    '': `1并购重组${d}.xlsx`,
    '并购重组': `1并购重组${d}.xlsx`,
    '股权转让': `2股权转让${d}.xlsx`,
    '增发实现': `3增发实现${d}.xlsx`,
    '申报并购重组': `4申报并购重组${d}.xlsx`,
    '质押': `5质押${d}.xlsx`,
    '减持叠加质押和大宗交易': `6减持叠加质押和大宗交易${d}.xlsx`,
    '招投标': `9招投标${d}.xlsx`,
  }
  return map[wt] || `1并购重组${d}.xlsx`
}

const onStepTypeChange = (step, index) => {
  step.config = {
    date_str: new Date().toISOString().split('T')[0],
    data_source_id: null,
    file_path: '',
    columns: [],
    output_filename: 'output_1.xlsx',
    apply_formatting: true,
    stock_code_column: '',
    date_column: '',
    use_fixed_columns: true,
    exclude_patterns_text: 'total_,output_',
    exclude_patterns: ['total_', 'output_']
  }
  if (step.type === 'match_sector') {
    const firstStepDate = form.value.steps[0]?.config?.date_str || new Date().toISOString().split('T')[0]
    step.config.output_filename = getDefaultFinalFilename(firstStepDate)
  }
  if (step.type === 'pledge_trend_analysis') {
    step.config = {
      trend_algo: 'mann_kendall',
      mk_pvalue: 0.05,
      b_max_reversals: 2,
      c_min_r2: 0.7,
      event_no_change_threshold: 0.5,
      event_large_threshold: 3.0,
      window_days: 365,
      row_recency_days: 30,
      output_filename: ''
    }
  }
  // 选择步骤类型后自动加载对应目录的已有文件
  if (['merge_excel', 'match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)) {
    fetchUploadedFiles(step, index)
  }
}

const onExcludePatternsChange = (step) => {
  const text = step.config.exclude_patterns_text || ''
  const patterns = text.split(',').map(p => p.trim()).filter(p => p)
  step.config.exclude_patterns = patterns
}

const onColumnModeChange = (step) => {
  if (step.config.use_fixed_columns) {
    step.config.columns = []
  }
}

const triggerFileInput = (index) => {
  const input = document.getElementById(`file-input-${index}`)
  if (input) {
    input.click()
  }
}

const onFileSelect = (event, step) => {
  const file = event.target.files[0]
  if (file) {
    step.config.file_path = file.name
    step.config.file_obj = file
  }
}

const fetchWorkflows = async () => {
  loading.value = true
  try {
    workflows.value = await api.get('/workflows/')
  } catch (error) {
    ElMessage.error('获取工作流失败')
  } finally {
    loading.value = false
  }
}

const fetchDataSources = async () => {
  try {
    dataSources.value = await api.get('/data-sources/')
  } catch (error) {
    console.error('获取数据源失败', error)
  }
}

const fetchWorkflowTypes = async () => {
  try {
    const response = await api.get('/workflows/types/')
    if (response?.success && response?.types) {
      workflowTypes.value = response.types
    }
  } catch (error) {
    console.error('获取工作流类型失败', error)
  }
}

const handleSave = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入工作流名称')
    return
  }

  if (form.value.steps.some(s => s.type === 'import_excel' && !s.config.file_path && !s.config.data_source_id)) {
    ElMessage.warning('导入Excel步骤必须选择文件或数据源')
    return
  }

  // 保存前：对 export_ma20_trend 步骤按 preset + date_str 重算范围
  form.value.steps.forEach(step => {
    if (step.type === 'export_ma20_trend' && step.config?.date_preset && step.config.date_preset !== 'custom') {
      const range = computeTrendDateRange(step.config.date_preset, step.config.date_str)
      step.config.date_range_start = range.start
      step.config.date_range_end = range.end
      step.config.date_range = null
    }
  })

  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
      workflow_type: form.value.workflow_type || '',
      steps: form.value.steps.map(step => ({
        type: step.type,
        config: step.config,
        status: step.status || 'pending'
      }))
    }

    if (isEditing.value && editingId.value) {
      await api.put(`/workflows/${editingId.value}`, payload)
      ElMessage.success('更新成功')
    } else {
      const created = await api.post('/workflows/', payload)
      editingId.value = created?.id || null
      ElMessage.success('创建成功')
    }

    const savedId = editingId.value
    showDialog.value = false
    await fetchWorkflows()
  } catch (error) {
    // 400 等错误已被 axios 拦截器通过 ElMessage.error 显示
    // 仅对拦截器未覆盖的情况补充提示
    if (!error?.response?.data?.detail) {
      ElMessage.error(isEditing.value ? '更新失败' : '创建失败')
    }
  }
}

const handleRun = (workflow) => {
  currentWorkflow.value = JSON.parse(JSON.stringify(workflow))
  executionStep.value = 0
  executionResult.value = null
  executionComplete.value = false
  hasDownloaded.value = false
  resultData.value = []
  resultColumns.value = []
  executionStartTime.value = null
  executionTime.value = '00:00:00'
  if (executionTimer.value) {
    clearInterval(executionTimer.value)
    executionTimer.value = null
  }
  showExecuteDialog.value = true
}

const startExecution = async () => {
  if (executing.value) return

  // 聚合类型（条件交集/导出20日均线趋势）：先检查数据可用性
  if (['条件交集', '导出20日均线趋势'].includes(currentWorkflow.value?.workflow_type)) {
    const dateStr = currentWorkflow.value.steps?.[0]?.config?.date_str
    if (!dateStr) {
      ElMessage.warning('工作流未设置数据日期')
      return
    }
    try {
      const availability = await api.get(`/workflows/check-data-availability/?date_str=${dateStr}`)
      if (availability.missing && availability.missing.length > 0) {
        const missingList = availability.missing.map(t => `  - ${t}`).join('\n')
        try {
          await ElMessageBox.confirm(
            `以下工作流缺少 ${dateStr} 数据：\n${missingList}\n\n缺失的类型将被跳过。是否继续？`,
            '数据缺失提醒',
            { type: 'warning', confirmButtonText: '继续', cancelButtonText: '取消' }
          )
        } catch {
          return // 用户取消
        }
      }
    } catch (error) {
      ElMessage.error('检查数据可用性失败')
      return
    }
  }

  executing.value = true
  executionResult.value = null
  resultData.value = []
  resultColumns.value = []
  executionStartTime.value = Date.now()
  if (executionTimer.value) {
    clearInterval(executionTimer.value)
  }
  executionTimer.value = setInterval(updateExecutionTime, 1000)
  updateExecutionTime()

  try {
    // 一键执行全部步骤（后端内存传递，无中间磁盘IO）
    executionAbortController.value = new AbortController()
    const response = await api.post(`/workflows/${currentWorkflow.value.id}/run/`, null, {
      signal: executionAbortController.value.signal
    })

    // 标记各步骤状态
    const stepResults = response.steps || []
    for (let i = 0; i < currentWorkflow.value.steps.length; i++) {
      const sr = stepResults[i]
      currentWorkflow.value.steps[i].status = sr ? sr.status : 'completed'
    }

    if (response.data?.records) {
      resultData.value = response.data.records.slice(0, 200)
    }
    if (response.data?.file_path) {
      executionResult.value = {
        type: 'success',
        message: response.message || '工作流执行完成',
        file_path: response.data.file_path,
        stats: response.data.stats,
        fail_samples: response.data.fail_samples,
        warnings: response.data.warnings
      }
    } else {
      executionResult.value = {
        type: 'success',
        message: response.message || '工作流执行完成',
        stats: response.data?.stats,
        fail_samples: response.data?.fail_samples,
        warnings: response.data?.warnings
      }
    }
    ElMessage.success(response.message || '工作流执行完成')
  } catch (error) {
    if (error?.code === 'ERR_CANCELED') return
    executionResult.value = {
      type: 'error',
      message: error.response?.data?.detail || '执行失败'
    }
  }

  executing.value = false
  executionComplete.value = true
  if (executionTimer.value) {
    clearInterval(executionTimer.value)
    executionTimer.value = null
  }
}

const downloadResult = async () => {
  if (!currentWorkflow.value?.id) {
    ElMessage.error('工作流信息不完整')
    return
  }
  try {
    await api.download(`/workflows/download-result/${currentWorkflow.value.id}`)
    hasDownloaded.value = true
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败', error)
    ElMessage.error('下载失败')
  }
}

const onExecuteDialogClose = () => {
  if (executionComplete.value && executionResult.value?.file_path && !hasDownloaded.value) {
    downloadResult()
  }
  const targetId = currentWorkflow.value?.id
  if (targetId) {
    setTimeout(() => highlightWorkflow(targetId), 300)
  }
}

const onEditDialogClose = () => {
  const targetId = editingId.value
  if (targetId) {
    // 延迟执行，确保 fetchWorkflows 完成 + DOM 更新后再高亮
    setTimeout(() => highlightWorkflow(targetId), 300)
  }
}

const downloadBatchResult = async (workflowId) => {
  try {
    await api.download(`/workflows/download-result/${workflowId}`)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败', error)
    ElMessage.error('下载失败')
  }
}

const onBatchDrawerClose = () => {
  stopBatchPolling()
  stopBatchTimer()
  // 自动下载所有已完成的工作流结果（错开300ms避免浏览器限流）
  const completedResults = (batchStatus.value?.results || []).filter(r => r.status === 'completed')
  if (completedResults.length) {
    ElMessage.info(`正在下载 ${completedResults.length} 个结果...`)
    completedResults.forEach((r, i) => {
      setTimeout(() => downloadBatchResult(r.workflow_id), i * 300)
    })
  }
}

const getTargetDirName = (stepType) => {
  const dirMap = {
    'merge_excel': '当日数据',
    'match_high_price': '百日新高',
    'match_ma20': '20日均线',
    'match_soe': '国企',
    'match_sector': '一级板块'
  }
  return dirMap[stepType] || '数据'
}

const getTargetDirDisplay = (stepType, dateStr) => {
  const workflowType = form.value.workflow_type || ''
  if (stepType === 'merge_excel') {
    if (workflowType === '股权转让') {
      return `股权转让/${dateStr || '当日数据'}/`
    }
    if (workflowType === '增发实现') {
      return `增发实现/${dateStr || '当日数据'}/`
    }
    if (workflowType === '申报并购重组') {
      return `申报并购重组/${dateStr || '当日数据'}/`
    }
    if (workflowType === '减持叠加质押和大宗交易') {
      return `减持叠加质押和大宗交易/${dateStr || '当日数据'}/`
    }
    if (workflowType === '招投标') {
      return `招投标/${dateStr || '当日数据'}/`
    }
    if (workflowType === '涨幅排名') {
      return `涨幅排名/${dateStr || '当日数据'}/`
    }
    if (workflowType === '质押') {
      return `质押/${dateStr || '当日数据'}/`
    }
    return `${dateStr || '当日数据'}/`
  }
  // match 步骤: 日期联动路径
  const firstDate = form.value.steps.find(s => s.config?.date_str)?.config?.date_str
  return `${firstDate || '当日数据'}/${getTargetDirName(stepType)}/`
}

const getPublicDirDisplay = () => {
  const workflowType = form.value.workflow_type || ''
  if (workflowType === '股权转让') {
    return '股权转让/public/'
  }
  if (workflowType === '增发实现') {
    return '增发实现/public/'
  }
  if (workflowType === '申报并购重组') {
    return '申报并购重组/public/'
  }
  if (workflowType === '减持叠加质押和大宗交易') {
    return '减持叠加质押和大宗交易/public/'
  }
  if (workflowType === '招投标') {
    return '招投标/public/'
  }
  if (workflowType === '涨幅排名') {
    const dateStr = form.value.steps.find(s => s.config?.date_str)?.config?.date_str || '当日数据'
    return `涨幅排名/${dateStr}/public/`
  }
  if (workflowType === '质押') {
    return '质押/public/'
  }
  return '2025public/'
}

const fetchUploadedFiles = async (step, index) => {
  const key = `step_${index}`
  // match 步骤使用第一步的日期
  const isMatchStep = ['match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)
  const dateStr = isMatchStep
    ? form.value.steps.find(s => s.config?.date_str)?.config?.date_str
    : step.config?.date_str
  try {
    const response = await api.get('/workflows/step-files/', {
      params: {
        step_type: step.type,
        date_str: dateStr,
        workflow_type: form.value.workflow_type || ''
      }
    })
    if (response?.files !== undefined) {
      uploadedFiles.value[key] = response.files
    }
  } catch (error) {
    console.error('获取上传文件失败', error)
    ElMessage.error('获取上传文件列表失败')
  }
}

const handleFileUpload = async (event, step, index) => {
  const file = event.target.files?.[0]
  if (!file) {
    return
  }

  const key = `step_${index}`
  uploadingSteps.value.add(key)

  const formData = new FormData()
  formData.append('file', file)
  formData.append('workflow_id', String(editingId.value || 0))
  formData.append('step_index', String(index))
  formData.append('step_type', step.type)
  formData.append('workflow_type', form.value.workflow_type || '')
  // match 步骤使用第一步的日期
  const isMatchStep = ['match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)
  const dateStr = isMatchStep
    ? form.value.steps.find(s => s.config?.date_str)?.config?.date_str
    : step.config?.date_str
  if (dateStr) {
    formData.append('date_str', dateStr)
  }


  try {
    const response = await api.post('/workflows/upload-step-file/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success('上传成功')
    await fetchUploadedFiles(step, index)
  } catch (error) {
    console.error('[Upload] Failed:', error)
    ElMessage.error('上传失败: ' + (error.message || '未知错误'))
  } finally {
    uploadingSteps.value.delete(key)
    event.target.value = ''
  }
}

const deleteUploadedFile = async (filePath, step, index) => {
  try {
    await ElMessageBox.confirm('确定删除此文件?', '提示', { type: 'warning' })
    await api.delete('/workflows/step-files/', {
      params: { file_path: filePath }
    })
    ElMessage.success('删除成功')
    await fetchUploadedFiles(step, index)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败', error)
      ElMessage.error('删除失败')
    }
  }
}

const previewFile = async (filePath) => {
  try {
    const response = await api.get('/workflows/step-files/preview', {
      params: { file_path: filePath }
    })
    if (response?.success) {
      previewData.value = response
      previewDialogVisible.value = true
    } else {
      ElMessage.error(response?.message || '预览失败')
    }
  } catch (error) {
    console.error('预览失败', error)
    ElMessage.error('预览失败')
  }
}

const fetchPublicFiles = async (step, index) => {
  const key = `step_${index}`
  try {
    const params = { workflow_type: form.value.workflow_type || '' }
    if (form.value.workflow_type === '涨幅排名') {
      params.date_str = step.config?.date_str || ''
    }
    const response = await api.get('/workflows/public-files/', { params })
    if (response?.files !== undefined) {
      publicFiles.value[key] = response.files
    }
  } catch (error) {
    console.error('获取公共文件列表失败', error)
  }
}

const triggerPublicFileInput = (index) => {
  document.getElementById(`public-file-input-${index}`)?.click()
}

const handlePublicFileUpload = async (event, step, index) => {
  const file = event.target.files?.[0]
  if (!file) return

  const key = `public_${index}`
  uploadingSteps.value.add(key)

  const formData = new FormData()
  formData.append('file', file)
  formData.append('workflow_type', form.value.workflow_type || '')
  if (form.value.workflow_type === '涨幅排名') {
    formData.append('date_str', step.config?.date_str || '')
  }

  try {
    const response = await api.post('/workflows/public-files/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    if (response?.success) {
      ElMessage.success('上传成功')
    } else {
      ElMessage.error(response?.message || '上传失败')
    }
    await fetchPublicFiles(step, index)
  } catch (error) {
    console.error('上传失败', error)
    ElMessage.error('上传失败')
    await fetchPublicFiles(step, index)
  } finally {
    uploadingSteps.value.delete(key)
    event.target.value = ''
  }
}

const previewPublicFile = async (filePath) => {
  try {
    const response = await api.get('/workflows/public-files/preview', {
      params: { file_path: filePath }
    })
    if (response?.success) {
      previewData.value = response
      previewDialogVisible.value = true
    } else {
      ElMessage.error(response?.message || '预览失败')
    }
  } catch (error) {
    console.error('预览失败', error)
    ElMessage.error('预览失败')
  }
}

const deletePublicFile = async (filePath, step, index) => {
  try {
    await ElMessageBox.confirm('确定删除此文件?', '提示', { type: 'warning' })
    await api.delete('/workflows/public-files/', {
      params: { file_path: filePath }
    })
    ElMessage.success('删除成功')
    await fetchPublicFiles(step, index)
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败', error)
      ElMessage.error('删除失败')
    }
  }
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const handleViewSteps = (workflow) => {
  currentWorkflow.value = workflow
  showStepsDialog.value = true
}

const handleEdit = (row) => {
  isEditing.value = true
  editingId.value = row.id
  loadingEditData.value = true
  form.value = {
    name: row.name,
    description: row.description || '',
    workflow_type: row.workflow_type || '',
    created_at: row.created_at || '',
    steps: (row.steps || []).map(step => ({
      type: step.type,
      config: { ...step.config },
      status: step.status || 'pending'
    }))
  }
  if (form.value.steps.length === 0) {
    form.value.steps = [defaultStep()]
  }
  // 对 export_ma20_trend 步骤：非 custom preset 时按 date_str 重算趋势范围
  form.value.steps.forEach(step => {
    if (step.type === 'export_ma20_trend' && step.config?.date_preset && step.config.date_preset !== 'custom') {
      const range = computeTrendDateRange(step.config.date_preset, step.config.date_str)
      step.config.date_range_start = range.start
      step.config.date_range_end = range.end
      step.config.date_range = null
    }
    // 对 condition_intersection 步骤：仅 1 条高价周期时自动同步 end 到 date_str
    if (step.type === 'condition_intersection' && step.config?.date_str) {
      const periods = step.config.high_price_periods || []
      if (periods.length === 1) {
        periods[0].end = step.config.date_str
      }
    }
  })
  showDialog.value = true
  // loadingEditData 必须在 nextTick 后关闭，否则 workflow_type watcher
  // 在微任务中触发时 loadingEditData 已为 false，会用默认步骤覆盖已保存的数据
  nextTick(() => {
    loadingEditData.value = false
  })

  uploadedFiles.value = {}
  publicFiles.value = {}
  const t = setTimeout(() => {
    form.value.steps.forEach((step, index) => {
      if (['merge_excel', 'match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)) {
        fetchUploadedFiles(step, index)
      }
      if (step.type === 'merge_excel') {
        fetchPublicFiles(step, index)
      }
    })
  }, 300)
  pendingTimeouts.value.push(t)
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除此工作流?', '提示', {
      type: 'warning'
    })
    await api.delete(`/workflows/${id}`)
    ElMessage.success('删除成功')
    fetchWorkflows()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchWorkflows()
  fetchDataSources()
  fetchWorkflowTypes()
})

onBeforeUnmount(() => {
  if (executionTimer.value) {
    clearInterval(executionTimer.value)
    executionTimer.value = null
  }
  if (highlightTimer.value) {
    clearTimeout(highlightTimer.value)
    highlightTimer.value = null
  }
  pendingTimeouts.value.forEach(t => clearTimeout(t))
  pendingTimeouts.value = []
  executionAbortController.value?.abort()
  stopBatchTimer()
  stopBatchPolling()
})

const handleSelectionChange = (rows) => {
  selectedWorkflows.value = rows
}

const getWorkflowName = (workflowId) => {
  const wf = workflows.value.find(w => w.id === workflowId)
  return wf ? wf.name : `工作流#${workflowId}`
}

const batchStatusText = (status) => {
  const map = { pending: '等待中', running: '执行中', completed: '已完成', partial: '部分成功', failed: '失败', cancelled: '已取消' }
  return map[status] || status
}

const batchStatusTagType = (status) => {
  const map = { pending: 'info', running: 'primary', completed: 'success', partial: 'warning', failed: 'danger', cancelled: 'info' }
  return map[status] || 'info'
}

const batchProgressStatus = computed(() => {
  if (!batchStatus.value.total) return undefined
  const s = batchStatus.value.status
  if (s === 'completed') return 'success'
  if (s === 'failed') return 'exception'
  return undefined
})

const formatElapsed = (seconds) => {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

const startBatchTimer = () => {
  stopBatchTimer()
  batchElapsedSeconds.value = 0
  batchTimerInterval.value = setInterval(() => {
    batchElapsedSeconds.value++
  }, 1000)
}

const stopBatchTimer = () => {
  if (batchTimerInterval.value) {
    clearInterval(batchTimerInterval.value)
    batchTimerInterval.value = null
  }
}

const handleBatchRun = async () => {
  if (selectedWorkflows.value.length === 0) {
    ElMessage.warning('请先选择要执行的工作流')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定并行执行 ${selectedWorkflows.value.length} 个工作流?`,
      '批量执行确认',
      { type: 'warning', confirmButtonText: '开始执行', cancelButtonText: '取消' }
    )
  } catch {
    return
  }

  batchExecuting.value = true
  batchStatus.value = { status: 'pending', total: selectedWorkflows.value.length, completed: 0, failed: 0, results: [] }
  batchProgressDrawer.value = true
  startBatchTimer()

  try {
    const response = await api.post('/workflows/batch-run/', {
      workflow_ids: selectedWorkflows.value.map(w => w.id)
    })
    if (response?.task_id) {
      batchStatus.value = { ...batchStatus.value, status: 'running', task_id: response.task_id }
      startBatchPolling(response.task_id)
    } else {
      throw new Error('未获取到任务ID')
    }
  } catch (error) {
    console.error('批量执行启动失败:', error)
    ElMessage.error('批量执行启动失败: ' + (error.message || '未知错误'))
    batchStatus.value = { ...batchStatus.value, status: 'failed' }
    batchExecuting.value = false
    stopBatchTimer()
  }
}

const startBatchPolling = (taskId) => {
  stopBatchPolling()
  const poll = async () => {
    try {
      const response = await api.get(`/workflows/batch-status/${taskId}/`)
      if (response) {
        batchStatus.value = response
        if (['completed', 'partial', 'failed', 'cancelled'].includes(response.status)) {
          batchPollingTimer.value = null
          stopBatchTimer()
          batchExecuting.value = false
          const msg = response.status === 'completed'
            ? '全部工作流执行完成'
            : response.status === 'partial'
              ? `部分完成: ${response.completed} 成功, ${response.failed} 失败`
              : '批量执行失败'
          ElMessage[response.status === 'completed' ? 'success' : 'warning'](msg)
          return
        }
      }
    } catch (error) {
      console.error('轮询批次状态失败:', error)
    }
    batchPollingTimer.value = setTimeout(poll, 2000)
  }
  batchPollingTimer.value = setTimeout(poll, 2000)
}

const stopBatchPolling = () => {
  if (batchPollingTimer.value) {
    clearTimeout(batchPollingTimer.value)
    batchPollingTimer.value = null
  }
}

watch(showDialog, (visible) => {
  if (!visible) {
    uploadedFiles.value = {}
    publicFiles.value = {}
  }
})

// 数据刷新后重新应用高亮（fetchWorkflows 会替换 DOM 元素）
watch(workflows, () => {
  if (highlightedWorkflowId.value) {
    nextTick(() => applyHighlightDOM(highlightedWorkflowId.value))
  }
})

watch(() => form.value.workflow_type, (newType, oldType) => {
  if (newType !== oldType && showDialog.value) {
    uploadedFiles.value = {}
    publicFiles.value = {}

    form.value.steps.forEach((step) => {
      if (step.type === 'match_sector') {
        const firstStepWithDate = form.value.steps.find(s => s.config?.date_str)
        const dateStr = firstStepWithDate?.config?.date_str || new Date().toISOString().split('T')[0]
        step.config.output_filename = getDefaultFinalFilename(dateStr)
      }
    })

    const t = setTimeout(() => {
      form.value.steps.forEach((step, index) => {
        if (['merge_excel', 'match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)) {
          fetchUploadedFiles(step, index)
        }
        if (step.type === 'merge_excel') {
          fetchPublicFiles(step, index)
        }
      })
    }, 100)
    pendingTimeouts.value.push(t)
  }
})

watch(
  () => ({
    dateStr: form.value.steps.find(s => s.config?.date_str)?.config?.date_str,
    lastType: form.value.steps[form.value.steps.length - 1]?.type,
    workflowType: form.value.workflow_type
  }),
  ({ dateStr, lastType, workflowType }) => {
    if (!dateStr) return
    const lastStep = form.value.steps[form.value.steps.length - 1]
    if (lastType === 'match_sector' && lastStep) {
      lastStep.config.output_filename = getDefaultFinalFilename(dateStr)
    }
    // 日期变化时刷新 match 步骤文件列表
    form.value.steps.forEach((step, index) => {
      if (['match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)) {
        fetchUploadedFiles(step, index)
      }
    })
  }
)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.steps-container {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 20px;
}

.step-item {
  margin-bottom: 15px;
}

.step-card {
  margin-bottom: 0;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-input-wrapper {
  display: flex;
  gap: 10px;
  align-items: center;
}

.file-input-wrapper .el-input {
  flex: 1;
}

.file-input {
  display: none;
}

.file-btn {
  flex-shrink: 0;
}

.upload-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.target-dir-info {
  margin-bottom: 5px;
}

.upload-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.uploaded-files-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: white;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.file-info .el-icon {
  color: #409eff;
  flex-shrink: 0;
}

.file-name {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}

.file-actions {
  display: flex;
  gap: 5px;
  flex-shrink: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.batch-progress-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 0 10px;
}

.batch-overview {
  margin-bottom: 10px;
}

.batch-results-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 200px;
}

.batch-result-item {
  padding: 10px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.result-error {
  margin-top: 5px;
  padding: 4px 8px;
  background: #fef0f0;
  border-radius: 4px;
}

.result-output {
  margin-top: 4px;
}

.batch-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 15px;
  border-top: 1px solid #e4e7ed;
  margin-top: 15px;
}

.pledge-summary-card {
  width: 100%;
  background: #fafbfc;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px 14px;
}
.pledge-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px 16px;
}
.pledge-row + .pledge-row {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e4e7ed;
}
.pledge-row-stats {
  font-size: 13px;
  color: #606266;
}
.pledge-row-stats .pledge-label {
  font-weight: 600;
  color: #303133;
  min-width: 72px;
}
.pledge-stat {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 2px 8px;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}
.pledge-stat b {
  color: #409EFF;
  font-weight: 600;
}
.fail-sample {
  padding: 4px 0;
  font-size: 12px;
  color: #606266;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.param-hint {
  color: #909399;
  font-size: 12px;
}

</style>
