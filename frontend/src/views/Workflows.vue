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

      <el-table :data="workflows" stripe v-loading="loading" @selection-change="handleSelectionChange" ref="workflowTableRef">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="name" label="工作流名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" />
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

    <el-dialog v-model="showDialog" :title="isEditing ? '编辑工作流' : '创建工作流'" width="800px">
      <el-form :model="form" label-width="140px">
        <el-form-item label="工作流名称">
          <el-input v-model="form.name" placeholder="请输入工作流名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="2" placeholder="请输入描述" />
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
                <el-select v-model="step.type" style="width: 100%" @change="onStepTypeChange(step)">
                  <el-option label="导入Excel" value="import_excel" />
                  <el-option label="合并当日数据源" value="merge_excel" />
                  <el-option label="智能去重" value="smart_dedup" />
                  <el-option label="提取列" value="extract_columns" />
                  <el-option label="导出Excel" value="export_excel" />
                  <el-option label="匹配百日新高" value="match_high_price" />
                  <el-option label="匹配20日均线" value="match_ma20" />
                  <el-option label="匹配国企" value="match_soe" />
                  <el-option label="匹配一级板块" value="match_sector" />
                  <el-option label="待定" value="pending" />
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
                    @change="fetchUploadedFiles(step, index)"
                  />
                </el-form-item>
                <el-form-item label="上传数据">
                  <div class="upload-section">
                    <div class="target-dir-info">
                      <el-tag type="info">目标目录: {{ step.config.date_str || '当日数据' }}/</el-tag>
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
                      <el-tag type="warning">公共目录: 2025public/ (与当日数据一起合并)</el-tag>
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
                <el-alert title="合并当日目录和2025public目录下所有Excel文件" type="info" :closable="false" />
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
                    <el-radio :value="true">固定4列</el-radio>
                    <el-radio :value="false">自定义列</el-radio>
                  </el-radio-group>
                </el-form-item>

                <template v-if="step.config.use_fixed_columns !== false">
                  <el-alert title="提取: 序号、证券代码、证券简称、最新公告日" type="success" :closable="false" />
                </template>
                <template v-else>
                  <el-form-item label="选择列">
                    <el-select v-model="step.config.columns" multiple style="width: 100%" placeholder="选择要提取的列">
                      <el-option label="序号" value="序号" />
                      <el-option label="证券代码" value="证券代码" />
                      <el-option label="证券简称" value="证券简称" />
                      <el-option label="最新公告日" value="最新公告日" />
                      <el-option label="其他可配置列..." value="__custom__" disabled />
                    </el-select>
                  </el-form-item>
                  <el-alert title="提示: 如需其他列名，请在config.columns中手动配置" type="info" :closable="false" />
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
                      <el-tag type="info">目标目录: 百日新高/</el-tag>
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
                      <el-tag type="info">目标目录: 20日均线/</el-tag>
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
                      <el-tag type="info">目标目录: 国企/</el-tag>
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
                      <el-tag type="info">目标目录: 一级板块/</el-tag>
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

              <template v-if="step.type === 'pending'">
                <el-alert title="此步骤暂未配置，待后续开发" type="info" :closable="false" />
              </template>
            </el-card>
          </div>
        </div>

        <el-form-item>
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

    <el-dialog v-model="showExecuteDialog" title="工作流执行" width="700px">
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

    <el-drawer v-model="batchProgressDrawer" title="并行执行进度" direction="rtl" size="450px" :close-on-press-escape="true" @close="stopBatchPolling">
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
            </div>
            <div v-if="result.error" class="result-error">
              <el-text type="danger" size="small">{{ result.error }}</el-text>
            </div>
            <div v-if="result.output_file" class="result-output">
              <el-text type="info" size="small">输出: {{ result.output_file }}</el-text>
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
import { ref, onMounted, computed, watch } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Timer, FolderOpened, Upload, Delete, View, Download, Document, Promotion, Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const showDialog = ref(false)
const showStepsDialog = ref(false)
const showExecuteDialog = ref(false)
const executing = ref(false)
const executionComplete = ref(false)
const executionStep = ref(0)
const executionResult = ref(null)
const resultData = ref([])
const resultColumns = ref([])
const workflows = ref([])
const dataSources = ref([])
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
const workflowTableRef = ref(null)

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
    pending: '待定'
  }
  return names[type] || type
}

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
  form.value = {
    name: '',
    description: '',
    steps: [defaultStep()]
  }
  showDialog.value = true
}

const addStep = () => {
  const newStep = defaultStep()
  if (newStep.type === 'match_sector') {
    const firstStepDate = form.value.steps[0]?.config?.date_str || new Date().toISOString().split('T')[0]
    newStep.config.output_filename = `并购重组${firstStepDate}.xlsx`
  }
  form.value.steps.push(newStep)
}

const removeStep = (index) => {
  form.value.steps.splice(index, 1)
}

const onStepTypeChange = (step) => {
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
    step.config.output_filename = `并购重组${firstStepDate}.xlsx`
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

const handleSave = async () => {
  if (!form.value.name) {
    ElMessage.warning('请输入工作流名称')
    return
  }

  if (form.value.steps.some(s => s.type === 'import_excel' && !s.config.file_path && !s.config.data_source_id)) {
    ElMessage.warning('导入Excel步骤必须选择文件或数据源')
    return
  }

  try {
    const payload = {
      name: form.value.name,
      description: form.value.description,
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
      await api.post('/workflows/', payload)
      ElMessage.success('创建成功')
    }

    showDialog.value = false
    fetchWorkflows()
  } catch (error) {
    ElMessage.error(isEditing.value ? '更新失败' : '创建失败')
  }
}

const handleRun = (workflow) => {
  currentWorkflow.value = JSON.parse(JSON.stringify(workflow))
  executionStep.value = 0
  executionResult.value = null
  executionComplete.value = false
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
  executing.value = true
  executionResult.value = null
  resultData.value = []
  resultColumns.value = []
  executionStartTime.value = Date.now()
  executionTimer.value = setInterval(updateExecutionTime, 1000)
  updateExecutionTime()

  for (let i = 0; i < currentWorkflow.value.steps.length; i++) {
    executionStep.value = i
    try {
      const response = await api.post(`/workflows/${currentWorkflow.value.id}/execute-step/`, {
        step_index: i
      })
      currentWorkflow.value.steps[i].status = 'completed'
      if (response.data?.records) {
        resultData.value = response.data.records
        resultColumns.value = response.data.columns || []
      }
    } catch (error) {
      if (executionTimer.value) {
        clearInterval(executionTimer.value)
        executionTimer.value = null
      }
      currentWorkflow.value.steps[i].status = 'failed'
      executionResult.value = {
        type: 'error',
        message: `步骤 ${i + 1} 执行失败`
      }
      executing.value = false
      return
    }
  }

  executing.value = false
  executionComplete.value = true
  if (executionTimer.value) {
    clearInterval(executionTimer.value)
    executionTimer.value = null
  }
  executionResult.value = {
    type: 'success',
    message: '工作流执行完成',
    file_path: '/app/data/excel/excel_2.xlsx'
  }
  ElMessage.success('工作流执行完成')
}

const downloadResult = async () => {
  if (!currentWorkflow.value?.id) {
    ElMessage.error('工作流信息不完整')
    return
  }
  try {
    const lastStep = currentWorkflow.value.steps.length - 1
    const filename = `workflow_result_${currentWorkflow.value.name}_${Date.now()}.xlsx`
    await api.download(`/workflows/download-result/${currentWorkflow.value.id}?step_index=${lastStep}`, filename)
    ElMessage.success('下载成功')
  } catch (error) {
    console.error('下载失败', error)
    ElMessage.error('下载失败')
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

const fetchUploadedFiles = async (step, index) => {
  const key = `step_${index}`
  try {
    const response = await api.get('/workflows/step-files/', {
      params: {
        step_type: step.type,
        date_str: step.config?.date_str
      }
    })
    console.log('[Debug] fetchUploadedFiles response:', response)
    if (response?.files !== undefined) {
      uploadedFiles.value[key] = response.files
      console.log('[Debug] uploadedFiles updated:', key, uploadedFiles.value[key])
    }
  } catch (error) {
    console.error('获取上传文件失败', error)
    ElMessage.error('获取上传文件列表失败')
  }
}

const handleFileUpload = async (event, step, index) => {
  const file = event.target.files?.[0]
  if (!file) {
    console.log('[Upload] No file selected')
    return
  }
  console.log('[Upload] File selected:', file.name, 'step_type:', step.type, 'date_str:', step.config?.date_str)

  const key = `step_${index}`
  uploadingSteps.value.add(key)

  const formData = new FormData()
  formData.append('file', file)
  formData.append('workflow_id', String(editingId.value || 0))
  formData.append('step_index', String(index))
  formData.append('step_type', step.type)
  if (step.config?.date_str) {
    formData.append('date_str', step.config.date_str)
  }

  console.log('[Upload] Sending request to /workflows/upload-step-file/')

  try {
    const response = await api.post('/workflows/upload-step-file/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    console.log('[Upload] Success:', response)
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
    const response = await api.get('/workflows/public-files/')
    console.log('[Debug] fetchPublicFiles response:', response)
    if (response?.files !== undefined) {
      publicFiles.value[key] = response.files
      console.log('[Debug] publicFiles updated:', key, publicFiles.value[key])
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

  try {
    const response = await api.post('/workflows/public-files/upload/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    console.log('[Debug] upload response:', response)
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
  console.log('[Debug] handleEdit called, row:', row)
  isEditing.value = true
  editingId.value = row.id
  form.value = {
    name: row.name,
    description: row.description || '',
    steps: (row.steps || []).map(step => ({
      type: step.type,
      config: { ...step.config },
      status: step.status || 'pending'
    }))
  }
  if (form.value.steps.length === 0) {
    form.value.steps = [defaultStep()]
  }
  showDialog.value = true

  uploadedFiles.value = {}
  publicFiles.value = {}
  setTimeout(() => {
    form.value.steps.forEach((step, index) => {
      if (['merge_excel', 'match_high_price', 'match_ma20', 'match_soe', 'match_sector'].includes(step.type)) {
        fetchUploadedFiles(step, index)
      }
      if (step.type === 'merge_excel') {
        fetchPublicFiles(step, index)
      }
    })
  }, 300)
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
  }
}

const startBatchPolling = (taskId) => {
  stopBatchPolling()
  batchPollingTimer.value = setInterval(async () => {
    try {
      const response = await api.get(`/workflows/batch-status/${taskId}/`)
      if (response) {
        batchStatus.value = response
        if (['completed', 'partial', 'failed', 'cancelled'].includes(response.status)) {
          stopBatchPolling()
          batchExecuting.value = false
          const msg = response.status === 'completed'
            ? '全部工作流执行完成'
            : response.status === 'partial'
              ? `部分完成: ${response.completed} 成功, ${response.failed} 失败`
              : '批量执行失败'
          ElMessage[response.status === 'completed' ? 'success' : 'warning'](msg)
        }
      }
    } catch (error) {
      console.error('轮询批次状态失败:', error)
    }
  }, 2000)
}

const stopBatchPolling = () => {
  if (batchPollingTimer.value) {
    clearInterval(batchPollingTimer.value)
    batchPollingTimer.value = null
  }
}

watch(() => form.value.steps, (steps) => {
  const firstStepWithDate = steps.find(s => s.config?.date_str)
  if (!firstStepWithDate) return
  const lastStep = steps[steps.length - 1]
  if (lastStep?.type === 'match_sector') {
    lastStep.config.output_filename = `并购重组${firstStepWithDate.config.date_str}.xlsx`
  }
}, { deep: true })
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
</style>
