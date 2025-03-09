export default {
  data() {
    return {
      orders: [],
      loading: false,
      dialogVisible: false,
      currentOrder: null,
      statusOptions: [
        { value: 'SUBMITTED', label: '已提交' },
        { value: 'FILLED', label: '已成交' },
        { value: 'PARTIALLY_FILLED', label: '部分成交' },
        { value: 'CANCELLED', label: '已取消' },
        { value: 'REJECTED', label: '已拒绝' }
      ]
    };
  },
  
  template: `
    <div>
      <div class="page-header">
        <h2 class="page-title">订单管理</h2>
        <el-button type="primary" @click="fetchOrders">刷新</el-button>
      </div>
      
      <el-card>
        <el-table
          v-loading="loading"
          :data="orders"
          style="width: 100%"
          border
        >
          <el-table-column prop="order_id" label="订单ID" width="120" />
          <el-table-column prop="symbol" label="股票代码" width="120" />
          <el-table-column label="方向" width="80">
            <template #default="scope">
              <el-tag :type="scope.row.direction === 'BUY' ? 'success' : 'danger'">
                {{ scope.row.direction === 'BUY' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="价格" width="100" />
          <el-table-column prop="quantity" label="数量" width="100" />
          <el-table-column label="状态" width="120">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">
                {{ getStatusText(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="create_time" label="创建时间" width="180" />
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-button type="primary" size="small" @click="viewOrder(scope.row)">详情</el-button>
              <el-button 
                type="warning" 
                size="small" 
                v-if="scope.row.status === 'SUBMITTED'"
                @click="cancelOrder(scope.row)"
              >
                取消
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      
      <!-- 订单详情对话框 -->
      <el-dialog
        v-model="dialogVisible"
        title="订单详情"
        width="50%"
      >
        <div v-if="currentOrder">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="订单ID">{{ currentOrder.order_id }}</el-descriptions-item>
            <el-descriptions-item label="股票代码">{{ currentOrder.symbol }}</el-descriptions-item>
            <el-descriptions-item label="方向">
              <el-tag :type="currentOrder.direction === 'BUY' ? 'success' : 'danger'">
                {{ currentOrder.direction === 'BUY' ? '买入' : '卖出' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="价格">{{ currentOrder.price }}</el-descriptions-item>
            <el-descriptions-item label="数量">{{ currentOrder.quantity }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentOrder.status)">
                {{ getStatusText(currentOrder.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ currentOrder.create_time }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ currentOrder.update_time }}</el-descriptions-item>
            <el-descriptions-item label="策略ID">{{ currentOrder.strategy_id }}</el-descriptions-item>
            <el-descriptions-item label="成交数量">{{ currentOrder.filled_quantity || 0 }}</el-descriptions-item>
            <el-descriptions-item label="成交均价">{{ currentOrder.avg_price || '-' }}</el-descriptions-item>
            <el-descriptions-item label="备注">{{ currentOrder.remark || '-' }}</el-descriptions-item>
          </el-descriptions>
          
          <div v-if="currentOrder.status === 'SUBMITTED'" class="mt-20">
            <el-divider>更新状态</el-divider>
            <el-form inline>
              <el-form-item label="新状态">
                <el-select v-model="newStatus">
                  <el-option 
                    v-for="option in statusOptions" 
                    :key="option.value" 
                    :label="option.label" 
                    :value="option.value" 
                  />
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="updateOrderStatus">更新</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-dialog>
    </div>
  `,
  
  mounted() {
    this.fetchOrders();
    
    // 监听订单更新
    window.addEventListener('order-update', this.handleOrderUpdate);
  },
  
  beforeUnmount() {
    window.removeEventListener('order-update', this.handleOrderUpdate);
  },
  
  methods: {
    async fetchOrders() {
      this.loading = true;
      try {
        const response = await axios.get('/admin/api/orders');
        this.orders = response.data;
      } catch (error) {
        console.error('获取订单列表失败:', error);
        this.$message.error('获取订单列表失败');
      } finally {
        this.loading = false;
      }
    },
    
    viewOrder(order) {
      this.currentOrder = order;
      this.newStatus = order.status;
      this.dialogVisible = true;
    },
    
    async cancelOrder(order) {
      try {
        await axios.put(`/admin/api/orders/${order.order_id}`, {
          status: 'CANCELLED'
        });
        this.$message.success('取消订单成功');
        this.fetchOrders();
      } catch (error) {
        console.error('取消订单失败:', error);
        this.$message.error('取消订单失败');
      }
    },
    
    async updateOrderStatus() {
      if (!this.currentOrder || !this.newStatus) return;
      
      try {
        await axios.put(`/admin/api/orders/${this.currentOrder.order_id}`, {
          status: this.newStatus
        });
        this.$message.success('更新状态成功');
        this.dialogVisible = false;
        this.fetchOrders();
      } catch (error) {
        console.error('更新订单状态失败:', error);
        this.$message.error('更新订单状态失败');
      }
    },
    
    handleOrderUpdate(event) {
      // 收到订单更新事件，刷新列表
      this.fetchOrders();
    },
    
    getStatusType(status) {
      switch (status) {
        case 'SUBMITTED':
          return 'info';
        case 'FILLED':
          return 'success';
        case 'PARTIALLY_FILLED':
          return 'warning';
        case 'CANCELLED':
          return 'danger';
        case 'REJECTED':
          return 'danger';
        default:
          return 'info';
      }
    },
    
    getStatusText(status) {
      switch (status) {
        case 'SUBMITTED':
          return '已提交';
        case 'FILLED':
          return '已成交';
        case 'PARTIALLY_FILLED':
          return '部分成交';
        case 'CANCELLED':
          return '已取消';
        case 'REJECTED':
          return '已拒绝';
        default:
          return status;
      }
    }
  }
}; 