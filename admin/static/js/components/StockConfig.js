export default {
  data() {
    return {
      stocks: [],
      loading: false,
      dialogVisible: false,
      isEdit: false,
      stockForm: {
        symbol: '',
        name: '',
        enabled: true,
        config: {
          high_open: {
            enabled: false,
            price_threshold: 1.02,
            high_open_ratio: 1.03,
            volume_check_window: 5,
            sell_ratios: [1.02, 1.03, 1.05],
            price_offsets: [0.01, 0.02]
          },
          strategies: {
            auto_trade: {
              enabled: false,
              params: {
                buy_threshold: 1.01,
                sell_threshold: 0.99
              }
            }
          }
        }
      },
      configJson: '',
      configDialogVisible: false,
      currentConfig: null
    };
  },
  
  template: `
    <div>
      <div class="page-header">
        <h2 class="page-title">股票配置管理</h2>
        <el-button type="primary" @click="showAddDialog">添加股票</el-button>
      </div>
      
      <el-card>
        <el-table
          v-loading="loading"
          :data="stocks"
          style="width: 100%"
          border
        >
          <el-table-column prop="symbol" label="股票代码" width="120" />
          <el-table-column prop="name" label="股票名称" width="150" />
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.enabled ? 'success' : 'info'">
                {{ scope.row.enabled ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="高开策略" width="100">
            <template #default="scope">
              <el-tag :type="getStrategyStatus(scope.row, 'high_open') ? 'success' : 'info'">
                {{ getStrategyStatus(scope.row, 'high_open') ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="自动交易" width="100">
            <template #default="scope">
              <el-tag :type="getStrategyStatus(scope.row, 'auto_trade') ? 'success' : 'info'">
                {{ getStrategyStatus(scope.row, 'auto_trade') ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="配置详情" min-width="200">
            <template #default="scope">
              <el-button type="primary" size="small" @click="viewConfig(scope.row)">查看配置</el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-button type="primary" size="small" @click="editStock(scope.row)">编辑</el-button>
              <el-button 
                type="success" 
                size="small" 
                v-if="!scope.row.enabled"
                @click="toggleStatus(scope.row, true)"
              >
                启用
              </el-button>
              <el-button 
                type="warning" 
                size="small" 
                v-if="scope.row.enabled"
                @click="toggleStatus(scope.row, false)"
              >
                禁用
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      
      <!-- 添加/编辑股票对话框 -->
      <el-dialog
        v-model="dialogVisible"
        :title="isEdit ? '编辑股票' : '添加股票'"
        width="50%"
      >
        <el-form :model="stockForm" label-width="120px">
          <el-form-item label="股票代码">
            <el-input v-model="stockForm.symbol" :disabled="isEdit" />
          </el-form-item>
          <el-form-item label="股票名称">
            <el-input v-model="stockForm.name" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="stockForm.enabled" />
          </el-form-item>
          
          <el-divider>策略配置</el-divider>
          
          <el-form-item label="高开策略">
            <el-switch v-model="stockForm.config.high_open.enabled" />
          </el-form-item>
          
          <el-form-item label="自动交易策略">
            <el-switch v-model="stockForm.config.strategies.auto_trade.enabled" />
          </el-form-item>
          
          <el-form-item label="配置JSON">
            <el-input
              type="textarea"
              v-model="configJson"
              :rows="10"
              @change="handleConfigJsonChange"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <span class="dialog-footer">
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="saveStock">保存</el-button>
          </span>
        </template>
      </el-dialog>
      
      <!-- 查看配置对话框 -->
      <el-dialog
        v-model="configDialogVisible"
        title="配置详情"
        width="50%"
      >
        <pre>{{ JSON.stringify(currentConfig, null, 2) }}</pre>
      </el-dialog>
    </div>
  `,
  
  mounted() {
    this.fetchStocks();
  },
  
  watch: {
    'stockForm.config': {
      handler(newVal) {
        this.configJson = JSON.stringify(newVal, null, 2);
      },
      deep: true
    }
  },
  
  methods: {
    async fetchStocks() {
      this.loading = true;
      try {
        const response = await axios.get('/admin/api/stocks');
        this.stocks = response.data;
      } catch (error) {
        console.error('获取股票列表失败:', error);
        this.$message.error('获取股票列表失败');
      } finally {
        this.loading = false;
      }
    },
    
    getStrategyStatus(stock, strategy) {
      if (strategy === 'high_open') {
        return stock.config?.high_open?.enabled || false;
      } else if (strategy === 'auto_trade') {
        return stock.config?.strategies?.auto_trade?.enabled || false;
      }
      return false;
    },
    
    showAddDialog() {
      this.isEdit = false;
      this.stockForm = {
        symbol: '',
        name: '',
        enabled: true,
        config: {
          high_open: {
            enabled: false,
            price_threshold: 1.02,
            high_open_ratio: 1.03,
            volume_check_window: 5,
            sell_ratios: [1.02, 1.03, 1.05],
            price_offsets: [0.01, 0.02]
          },
          strategies: {
            auto_trade: {
              enabled: false,
              params: {
                buy_threshold: 1.01,
                sell_threshold: 0.99
              }
            }
          }
        }
      };
      this.configJson = JSON.stringify(this.stockForm.config, null, 2);
      this.dialogVisible = true;
    },
    
    editStock(stock) {
      this.isEdit = true;
      this.stockForm = JSON.parse(JSON.stringify(stock));
      this.configJson = JSON.stringify(stock.config, null, 2);
      this.dialogVisible = true;
    },
    
    viewConfig(stock) {
      this.currentConfig = stock.config;
      this.configDialogVisible = true;
    },
    
    handleConfigJsonChange() {
      try {
        this.stockForm.config = JSON.parse(this.configJson);
      } catch (error) {
        this.$message.error('JSON格式不正确');
      }
    },
    
    async saveStock() {
      try {
        if (this.isEdit) {
          // 更新股票
          await axios.put(`/admin/api/stocks/${this.stockForm.symbol}`, {
            name: this.stockForm.name,
            enabled: this.stockForm.enabled,
            config: this.stockForm.config
          });
          this.$message.success('更新成功');
        } else {
          // 创建股票
          await axios.post('/admin/api/stocks', this.stockForm);
          this.$message.success('添加成功');
        }
        this.dialogVisible = false;
        this.fetchStocks();
      } catch (error) {
        console.error('保存股票失败:', error);
        this.$message.error('保存失败');
      }
    },
    
    async toggleStatus(stock, enabled) {
      try {
        await axios.put(`/admin/api/stocks/${stock.symbol}`, {
          enabled: enabled
        });
        this.$message.success(`${enabled ? '启用' : '禁用'}成功`);
        this.fetchStocks();
      } catch (error) {
        console.error('更新状态失败:', error);
        this.$message.error('更新状态失败');
      }
    }
  }
}; 