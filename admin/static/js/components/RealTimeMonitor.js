export default {
  data() {
    return {
      marketData: {},
      chartInstance: null,
      selectedSymbol: '',
      priceHistory: {},
      maxDataPoints: 100
    };
  },
  
  template: `
    <div>
      <div class="page-header">
        <h2 class="page-title">实时监控</h2>
        <el-select v-model="selectedSymbol" placeholder="选择股票" style="width: 200px;">
          <el-option
            v-for="(data, symbol) in marketData"
            :key="symbol"
            :label="symbol"
            :value="symbol"
          />
        </el-select>
      </div>
      
      <el-row :gutter="20">
        <el-col :span="24">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>市场数据</span>
              </div>
            </template>
            <el-table
              :data="marketDataArray"
              style="width: 100%"
              border
            >
              <el-table-column prop="symbol" label="股票代码" width="120" />
              <el-table-column label="最新价" width="100">
                <template #default="scope">
                  {{ formatPrice(scope.row.price) }}
                </template>
              </el-table-column>
              <el-table-column label="涨跌" width="100">
                <template #default="scope">
                  <span :style="{ color: getPriceChangeColor(scope.row) }">
                    {{ getPriceChange(scope.row) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="成交量" width="120">
                <template #default="scope">
                  {{ formatVolume(scope.row.volume) }}
                </template>
              </el-table-column>
              <el-table-column label="最高" width="100">
                <template #default="scope">
                  {{ formatPrice(scope.row.high) }}
                </template>
              </el-table-column>
              <el-table-column label="最低" width="100">
                <template #default="scope">
                  {{ formatPrice(scope.row.low) }}
                </template>
              </el-table-column>
              <el-table-column label="更新时间" width="180">
                <template #default="scope">
                  {{ formatTime(scope.row.lastUpdate) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
      
      <el-row :gutter="20" class="mt-20">
        <el-col :span="24">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>价格走势</span>
              </div>
            </template>
            <div id="price-chart" style="width: 100%; height: 400px;"></div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  `,
  
  computed: {
    marketDataArray() {
      return Object.entries(this.marketData).map(([symbol, data]) => ({
        symbol,
        ...data
      }));
    }
  },
  
  watch: {
    selectedSymbol(newVal) {
      this.updateChart();
    }
  },
  
  mounted() {
    // 初始化图表
    this.initChart();
    
    // 监听市场数据更新
    window.addEventListener('market-data-update', this.handleMarketDataUpdate);
    
    // 获取初始市场数据
    this.marketData = window.wsManager?.marketData || {};
    
    // 如果有数据，选择第一个股票
    if (Object.keys(this.marketData).length > 0) {
      this.selectedSymbol = Object.keys(this.marketData)[0];
    }
  },
  
  beforeUnmount() {
    window.removeEventListener('market-data-update', this.handleMarketDataUpdate);
    if (this.chartInstance) {
      this.chartInstance.dispose();
    }
  },
  
  methods: {
    initChart() {
      const chartDom = document.getElementById('price-chart');
      this.chartInstance = echarts.init(chartDom);
      
      const option = {
        title: {
          text: '价格走势'
        },
        tooltip: {
          trigger: 'axis'
        },
        xAxis: {
          type: 'time',
          splitLine: {
            show: false
          }
        },
        yAxis: {
          type: 'value',
          scale: true,
          splitLine: {
            show: true
          }
        },
        series: [{
          name: '价格',
          type: 'line',
          data: [],
          showSymbol: false,
          lineStyle: {
            width: 2
          }
        }]
      };
      
      this.chartInstance.setOption(option);
    },
    
    updateChart() {
      if (!this.chartInstance || !this.selectedSymbol) return;
      
      const data = this.priceHistory[this.selectedSymbol] || [];
      
      const option = {
        title: {
          text: `${this.selectedSymbol} 价格走势`
        },
        series: [{
          name: '价格',
          data: data.map(item => [item.time, item.price])
        }]
      };
      
      this.chartInstance.setOption(option);
    },
    
    handleMarketDataUpdate(event) {
      const data = event.detail;
      
      // 更新市场数据
      this.marketData = window.wsManager?.marketData || {};
      
      // 更新价格历史
      if (data.symbol && data.price) {
        if (!this.priceHistory[data.symbol]) {
          this.priceHistory[data.symbol] = [];
        }
        
        this.priceHistory[data.symbol].push({
          time: new Date(),
          price: data.price
        });
        
        // 限制数据点数量
        if (this.priceHistory[data.symbol].length > this.maxDataPoints) {
          this.priceHistory[data.symbol].shift();
        }
        
        // 如果是当前选中的股票，更新图表
        if (data.symbol === this.selectedSymbol) {
          this.updateChart();
        }
        
        // 如果没有选中股票，选择第一个
        if (!this.selectedSymbol && Object.keys(this.marketData).length > 0) {
          this.selectedSymbol = Object.keys(this.marketData)[0];
        }
      }
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
    },
    
    formatTime(time) {
      if (!time) return '-';
      const date = new Date(time);
      return date.toLocaleTimeString();
    },
    
    getPriceChange(data) {
      if (!data.price || !data.open) return '-';
      const change = data.price - data.open;
      const changePercent = (change / data.open * 100).toFixed(2);
      return `${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePercent}%)`;
    },
    
    getPriceChangeColor(data) {
      if (!data.price || !data.open) return '';
      return data.price >= data.open ? '#f56c6c' : '#67c23a';
    }
  }
}; 