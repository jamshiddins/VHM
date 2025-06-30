'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Overview } from '@/components/dashboard/overview'
import { RecentSales } from '@/components/dashboard/recent-sales'
import { MachineStatus } from '@/components/dashboard/machine-status'
import { TasksWidget } from '@/components/dashboard/tasks-widget'
import { 
  Activity, 
  CreditCard, 
  DollarSign, 
  Package,
  Coffee,
  AlertTriangle,
  TrendingUp,
  Users
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { getDashboardStats } from '@/lib/api/dashboard'
import { Skeleton } from '@/components/ui/skeleton'
import { motion } from 'framer-motion'

const container = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1
    }
  }
}

const item = {
  hidden: { y: 20, opacity: 0 },
  show: { y: 0, opacity: 1 }
}

export default function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
    refetchInterval: 30000 // Обновление каждые 30 секунд
  })

  if (isLoading) {
    return <DashboardSkeleton />
  }

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Дашборд</h2>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-muted-foreground">
            Обновлено: {new Date().toLocaleTimeString('ru-RU')}
          </span>
        </div>
      </div>
      
      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
      >
        <motion.div variants={item}>
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Общий доход
              </CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.totalRevenue?.toLocaleString('ru-RU')} UZS
              </div>
              <p className="text-xs text-muted-foreground">
                <span className="text-green-500">+{stats?.revenueGrowth}%</span> к прошлому месяцу
              </p>
            </CardContent>
          </Card>
        </motion.div>
        
        <motion.div variants={item}>
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Продажи сегодня
              </CardTitle>
              <Coffee className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.salesToday}</div>
              <p className="text-xs text-muted-foreground">
                <span className="text-green-500">+{stats?.salesGrowth}%</span> к вчера
              </p>
            </CardContent>
          </Card>
        </motion.div>
        
        <motion.div variants={item}>
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Активные автоматы
              </CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.activeMachines}/{stats?.totalMachines}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats?.machinesNeedService} требуют обслуживания
              </p>
            </CardContent>
          </Card>
        </motion.div>
        
        <motion.div variants={item}>
          <Card className="border-0 shadow-lg hover:shadow-xl transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Критические остатки
              </CardTitle>
              <AlertTriangle className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.criticalStock}</div>
              <p className="text-xs text-muted-foreground">
                позиций требуют пополнения
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </motion.div>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4 border-0 shadow-lg">
          <CardHeader>
            <CardTitle>Обзор продаж</CardTitle>
          </CardHeader>
          <CardContent className="pl-2">
            <Overview data={stats?.salesOverview} />
          </CardContent>
        </Card>
        
        <Card className="col-span-3 border-0 shadow-lg">
          <CardHeader>
            <CardTitle>Последние продажи</CardTitle>
            <CardDescription>
              За последние 24 часа выполнено {stats?.recentSalesCount} продаж
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RecentSales sales={stats?.recentSales} />
          </CardContent>
        </Card>
      </div>
      
      <div className="grid gap-4 md:grid-cols-2">
        <MachineStatus />
        <TasksWidget />
      </div>
    </div>
  )
}

function DashboardSkeleton() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i} className="border-0 shadow-lg">
            <CardHeader className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-32" />
            </CardHeader>
          </Card>
        ))}
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4 border-0 shadow-lg">
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
        <Card className="col-span-3 border-0 shadow-lg">
          <CardHeader>
            <Skeleton className="h-6 w-32" />
          </CardHeader>
          <CardContent>
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
      </div>
    </div>
  )
}