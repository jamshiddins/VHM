'use client'

import { useState } from 'react'
import { Plus, Map, Grid3X3, Search, Filter } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { MachineCard } from '@/components/machines/machine-card'
import { MachineTable } from '@/components/machines/machine-table'
import { MachineMap } from '@/components/machines/machine-map'
import { MachineFilters } from '@/components/machines/machine-filters'
import { CreateMachineDialog } from '@/components/machines/create-machine-dialog'
import { useQuery } from '@tanstack/react-query'
import { getMachines } from '@/lib/api/machines'
import { Skeleton } from '@/components/ui/skeleton'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '@/components/ui/badge'

export default function MachinesPage() {
  const [view, setView] = useState<'grid' | 'table' | 'map'>('grid')
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({
    type: 'all',
    status: 'all',
    hasIssues: false
  })
  const [showFilters, setShowFilters] = useState(false)
  const [showCreateDialog, setShowCreateDialog] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['machines', filters, search],
    queryFn: () => getMachines({ ...filters, search })
  })

  const machines = data?.items || []
  const total = data?.total || 0

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Автоматы</h2>
          <p className="text-muted-foreground">
            Управление сетью вендинговых автоматов
          </p>
        </div>
        <Button 
          onClick={() => setShowCreateDialog(true)}
          className="gap-2"
        >
          <Plus className="h-4 w-4" />
          Добавить автомат
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Всего автоматов</span>
            <Badge variant="secondary">{total}</Badge>
          </div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Активные</span>
            <Badge variant="default" className="bg-green-500">
              {machines.filter(m => m.status === 'active').length}
            </Badge>
          </div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">На обслуживании</span>
            <Badge variant="secondary" className="bg-yellow-500">
              {machines.filter(m => m.status === 'maintenance').length}
            </Badge>
          </div>
        </div>
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Требуют внимания</span>
            <Badge variant="destructive">
              {machines.filter(m => m.hasIssues).length}
            </Badge>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Поиск по коду или адресу..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8"
          />
        </div>
        
        <Button
          variant="outline"
          size="icon"
          onClick={() => setShowFilters(!showFilters)}
          className={showFilters ? 'bg-accent' : ''}
        >
          <Filter className="h-4 w-4" />
        </Button>

        <Tabs value={view} onValueChange={(v) => setView(v as any)}>
          <TabsList>
            <TabsTrigger value="grid" className="gap-2">
              <Grid3X3 className="h-4 w-4" />
              <span className="hidden sm:inline">Сетка</span>
            </TabsTrigger>
            <TabsTrigger value="table" className="gap-2">
              <Grid3X3 className="h-4 w-4 rotate-90" />
              <span className="hidden sm:inline">Таблица</span>
            </TabsTrigger>
            <TabsTrigger value="map" className="gap-2">
              <Map className="h-4 w-4" />
              <span className="hidden sm:inline">Карта</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Filters */}
      <AnimatePresence>
        {showFilters && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <MachineFilters 
              filters={filters} 
              onChange={setFilters} 
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Content */}
      {isLoading ? (
        <MachinesLoadingSkeleton view={view} />
      ) : (
        <div className="mt-6">
          {view === 'grid' && (
            <motion.div 
              className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              {machines.map((machine, index) => (
                <motion.div
                  key={machine.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <MachineCard machine={machine} />
                </motion.div>
              ))}
            </motion.div>
          )}
          
          {view === 'table' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <MachineTable machines={machines} />
            </motion.div>
          )}
          
          {view === 'map' && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
              className="h-[600px] rounded-lg overflow-hidden"
            >
              <MachineMap machines={machines} />
            </motion.div>
          )}
        </div>
      )}

      {/* Create Dialog */}
      <CreateMachineDialog 
        open={showCreateDialog} 
        onOpenChange={setShowCreateDialog} 
      />
    </div>
  )
}

function MachinesLoadingSkeleton({ view }: { view: string }) {
  if (view === 'grid') {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {[...Array(8)].map((_, i) => (
          <Skeleton key={i} className="h-48" />
        ))}
      </div>
    )
  }
  
  if (view === 'table') {
    return <Skeleton className="h-96 w-full" />
  }
  
  return <Skeleton className="h-[600px] w-full" />
}