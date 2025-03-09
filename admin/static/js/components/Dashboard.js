export default {
  data() {
    return {
      systemStatus: {
        engine_running: false,
        strategies_count: 0
      },
      messages: [],
      marketData: {}
    };
  },
  
  template: `
    <div>
      <div class="page-header">
        <h2 class="page-title">系统仪表盘</h2>
        <el-button type="primary" @click="refreshStatus">刷新状态</el-button>
      </div>
      
      <div class="data-overview">
        <el-card class="data-card">
          <div class="data-label">引擎状态</div>
          <div class="data-value">
            <el-tag :type="systemStatus.engine_running ? 'success' : 'danger'">
              {{ systemStatus.engine_running ? '运行中' : '已停止' }}
            </el-tag>
          </div>
        </el-card>
        
        <el-card class="data-card">
          <div class="data-label">策略数量</div>
          <div class="data-value">{{ systemStatus.strategies_count }}</div>
        </el-card>
        
        <el-card class="data-card">
          <div class="data-label">WebSocket</div>
          <div class="data-value">
            <el-tag :type="wsConnected ? 'success' : 'danger'">
              {{ wsConnected ? '已连接' : '未连接' }}
            </el-tag>
          </div>
        </el-card>
      </div>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>实时消息</span>
              </div>
            </template>
            <div class="message-list">
              <div v-for="msg in latestMessages" :key="msg.id" class="message-item">
                <el-tag size="small" :type="getMessageType(msg.type)">{{ msg.type }}</el-tag>
                <span class="message-time">{{ formatTime(msg.time) }}</span>
                <div class="message-content">{{ JSON.stringify(msg.data) }}</div>
              </div>
              <el-empty v-if="latestMessages.length === 0" description="暂无消息" />
            </div>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>市场概览</span>
              </div>
            </template>
            <div v-if="Object.keys(marketData).length > 0">
              <div v-for="(data, symbol) in marketData" :key="symbol" class="market-item">
                <h4>{{ symbol }}</h4>
                <p>价格: {{ formatPrice(data.price) }}</p>
                <p>成交量: {{ formatVolume(data.volume) }}</p>
                <p>更新时间: {{ formatTime(data.lastUpdate) }}</p>
              </div>
            </div>
            <el-empty v-else description="暂无市场数据" />
          </el-card>
        </el-col>
      </el-row>
    </div>
  `,
  
  computed: {
    wsConnected() {
      return window.wsManager?.connected || false;
    },
    
    latestMessages() {
      return (window.wsManager?.messages || []).slice(-10).reverse();
    }
  },
  
  mounted() {
    this.refreshStatus();
    
    // 监听WebSocket消息
    window.addEventListener('ws-message', this.handleWsMessage);
    window.addEventListener('market-data-update', this.handleMarketDataUpdate);
  },
  
  beforeUnmount() {
    window.removeEventListener('ws-message', this.handleWsMessage);
    window.removeEventListener('market-data-update', this.handleMarketDataUpdate);
  },
  
  methods: {
    async refreshStatus() {
      try {
        const response = await axios.get('/health');
        this.systemStatus = response.data;
      } catch (error) {
        console.error('获取系统状态失败:', error);
        this.$message.error('获取系统状态失败');
      }
    },
    
    handleWsMessage(event) {
      // 更新消息列表
      this.messages = window.wsManager?.messages || [];
    },
    
    handleMarketDataUpdate(event) {
      // 更新市场数据
      this.marketData = window.wsManager?.marketData || {};
    },
    
    getMessageType(type) {
      switch (type) {
        case 'market_data':
          return 'success';
        case 'order_update':
          return 'warning';
        case 'system_status':
          return 'info';
        default:
          return 'info';
      }
    },
    
    formatTime(time) {
      if (!time) return '-';
      const date = new Date(time);
      return date.toLocaleTimeString();
    },
    
    formatPrice(price) {
      if (!price) return '-';
      return price.toFixed(2);
    },
    
    formatVolume(volume) {
      if (!volume) return '-';
      return volume >= 10000 
        ? (volume / 10000).toFixed(2) + '万' 
        : volume.toString();
    }
  }
}; 