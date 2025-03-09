// 导入组件
import Dashboard from './components/Dashboard.js';
import StockConfig from './components/StockConfig.js';
import OrderManagement from './components/OrderManagement.js';
import RealTimeMonitor from './components/RealTimeMonitor.js';

// 创建路由
const routes = [
  { path: '/', component: Dashboard },
  { path: '/stocks', component: StockConfig },
  { path: '/orders', component: OrderManagement },
  { path: '/monitor', component: RealTimeMonitor }
];

const router = VueRouter.createRouter({
  history: VueRouter.createWebHashHistory(),
  routes
});

// WebSocket管理
const wsManager = {
  ws: null,
  connected: false,
  messages: [],
  marketData: {},
  orderUpdates: [],
  
  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    this.ws = new WebSocket(wsUrl);
    
    this.ws.onopen = () => {
      console.log('WebSocket连接已建立');
      this.connected = true;
    };
    
    this.ws.onclose = () => {
      console.log('WebSocket连接已关闭');
      this.connected = false;
      // 尝试重连
      setTimeout(() => this.connect(), 3000);
    };
    
    this.ws.onerror = (error) => {
      console.error('WebSocket错误:', error);
    };
    
    this.ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      console.log('收到消息:', message);
      
      // 添加到消息历史
      this.messages.push({
        id: Date.now(),
        time: new Date(),
        type: message.type,
        data: message.data
      });
      
      // 限制消息历史数量
      if (this.messages.length > 100) {
        this.messages.shift();
      }
      
      // 处理不同类型的消息
      switch (message.type) {
        case 'market_data':
          this.updateMarketData(message.data);
          break;
        case 'order_update':
          this.updateOrderData(message.data);
          break;
      }
      
      // 触发事件，通知组件更新
      window.dispatchEvent(new CustomEvent('ws-message', { detail: message }));
    };
  },
  
  updateMarketData(data) {
    if (data.symbol) {
      this.marketData[data.symbol] = {
        ...this.marketData[data.symbol],
        ...data,
        lastUpdate: new Date()
      };
      
      // 触发市场数据更新事件
      window.dispatchEvent(new CustomEvent('market-data-update', { detail: data }));
    }
  },
  
  updateOrderData(data) {
    if (data.order_id) {
      // 查找是否已存在该订单
      const index = this.orderUpdates.findIndex(order => order.order_id === data.order_id);
      
      if (index >= 0) {
        // 更新现有订单
        this.orderUpdates[index] = {
          ...this.orderUpdates[index],
          ...data,
          lastUpdate: new Date()
        };
      } else {
        // 添加新订单
        this.orderUpdates.push({
          ...data,
          lastUpdate: new Date()
        });
      }
      
      // 触发订单更新事件
      window.dispatchEvent(new CustomEvent('order-update', { detail: data }));
    }
  }
};

// 创建Vue应用
const app = Vue.createApp({
  data() {
    return {
      activeIndex: '/',
      wsConnected: false
    };
  },
  
  computed: {
    currentRoutePath() {
      return this.$route.path;
    }
  },
  
  template: `
    <el-container>
      <el-aside width="200px">
        <div class="logo">交易系统</div>
        <el-menu
          :default-active="currentRoutePath"
          class="el-menu-vertical"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
          router
        >
          <el-menu-item index="/">
            <el-icon><el-icon-odometer /></el-icon>
            <span>仪表盘</span>
          </el-menu-item>
          <el-menu-item index="/stocks">
            <el-icon><el-icon-document /></el-icon>
            <span>股票配置</span>
          </el-menu-item>
          <el-menu-item index="/orders">
            <el-icon><el-icon-shopping-cart /></el-icon>
            <span>订单管理</span>
          </el-menu-item>
          <el-menu-item index="/monitor">
            <el-icon><el-icon-monitor /></el-icon>
            <span>实时监控</span>
          </el-menu-item>
        </el-menu>
      </el-aside>
      
      <el-container>
        <el-header>
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
                <el-breadcrumb-item v-if="$route.path !== '/'">{{ getPageTitle($route.path) }}</el-breadcrumb-item>
              </el-breadcrumb>
            </div>
            <div>
              <span class="status-badge" :class="wsConnected ? 'status-online' : 'status-offline'"></span>
              <span>{{ wsConnected ? '已连接' : '未连接' }}</span>
            </div>
          </div>
        </el-header>
        
        <el-main>
          <router-view></router-view>
        </el-main>
      </el-container>
    </el-container>
  `,
  
  methods: {
    getPageTitle(path) {
      const pathMap = {
        '/': '仪表盘',
        '/stocks': '股票配置',
        '/orders': '订单管理',
        '/monitor': '实时监控'
      };
      return pathMap[path] || '未知页面';
    }
  },
  
  mounted() {
    // 连接WebSocket
    wsManager.connect();
    
    // 监听WebSocket连接状态
    setInterval(() => {
      this.wsConnected = wsManager.connected;
    }, 1000);
  }
});

// 注册Element Plus组件和图标
for (const [key, component] of Object.entries(ElementPlus)) {
  app.component(key, component);
}

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

// 使用路由
app.use(router);

// 挂载应用
app.mount('#app'); 