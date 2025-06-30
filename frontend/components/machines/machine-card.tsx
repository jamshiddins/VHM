'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardFooter, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { 
  MoreVertical, 
  MapPin, 
  Activity, 
  AlertTriangle,
  Coffee,
  Package,
  Wrench,
  Power,
  PowerOff,
  Edit,
  Trash,
  BarChart3,
  Users
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Machine, MachineStatus, MachineType } from '@/types/machine'
import { motion } from 'framer-motion'
import { updateMachine, deleteMachine } from '@/lib/api/machines'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from '@/components/ui/use-toast'

interface MachineCardProps {
  machine: Machine
}

const typeIcons = {
  coffee: Coffee,
  snack: Package,
  combo: Coffee,
  water: Package,
}

const statusColors = {
  active: 'bg-green-500',
  maintenance: 'bg-yellow-500',
  inactive: 'bg-gray-500',
  broken: 'bg-red-500',
}

const statusLabels = {
  active: 'Активен',
  maintenance: 'Обслуживание',
  inactive: 'Неактивен',
  broken: 'Сломан',
}

export function MachineCard({ machine }: MachineCardProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)
  
  const TypeIcon = typeIcons[machine.type] || Coffee
  
  const updateStatusMutation = useMutation({
    mutationFn: (status: MachineStatus) => 
      updateMachine(machine.id, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['machines'] })
      toast({
        title: 'Статус обновлен',
        description: 'Статус автомата успешно изменен',
      })
    },
    onError: () => {
      toast({
        title: 'Ошибка',
        description: 'Не удалось обновить статус',
        variant: 'destructive',
      })
    }
  })
  
  const deleteMutation = useMutation({
    mutationFn: () => deleteMachine(machine.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['machines'] })
      toast({
        title: 'Автомат удален',
        description: 'Автомат успешно удален из системы',
      })
      setShowDeleteDialog(false)
    },
    onError: () => {
      toast({
        title: 'Ошибка',
        description: 'Не удалось удалить автомат',
        variant: 'destructive',
      })
    }
  })
  
  const handleStatusChange = (status: MachineStatus) => {
    updateStatusMutation.mutate(status)
  }
  
  const handleDelete = () => {
    deleteMutation.mutate()
  }
  
  return (
    <>
      <motion.div
        whileHover={{ y: -4 }}
        transition={{ duration: 0.2 }}
      >
        <Card 
          className={cn(
            "relative overflow-hidden cursor-pointer transition-all duration-200",
            "hover:shadow-lg dark:hover:shadow-primary/20",
            machine.hasIssues && "border-destructive"
          )}
          onClick={() => router.push(`/machines/${machine.id}`)}
        >
          {/* Status indicator */}
          <div className={cn(
            "absolute top-0 right-0 w-24 h-24 -mr-12 -mt-12 rounded-full blur-2xl opacity-20",
            statusColors[machine.status]
          )} />
          
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "p-2 rounded-lg",
                  machine.status === 'active' ? 'bg-primary/10' : 'bg-muted'
                )}>
                  <TypeIcon className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle className="text-lg">{machine.code}</CardTitle>
                  <CardDescription className="text-xs">
                    {machine.name}
                  </CardDescription>
                </div>
              </div>
              
              <DropdownMenu>
                <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation()
                    router.push(`/machines/${machine.id}/edit`)
                  }}>
                    <Edit className="mr-2 h-4 w-4" />
                    Редактировать
                  </DropdownMenuItem>
                  
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation()
                    router.push(`/machines/${machine.id}/stats`)
                  }}>
                    <BarChart3 className="mr-2 h-4 w-4" />
                    Статистика
                  </DropdownMenuItem>
                  
                  <DropdownMenuSeparator />
                  
                  {machine.status === 'active' ? (
                    <DropdownMenuItem onClick={(e) => {
                      e.stopPropagation()
                      handleStatusChange('inactive')
                    }}>
                      <PowerOff className="mr-2 h-4 w-4" />
                      Деактивировать
                    </DropdownMenuItem>
                  ) : (
                    <DropdownMenuItem onClick={(e) => {
                      e.stopPropagation()
                      handleStatusChange('active')
                    }}>
                      <Power className="mr-2 h-4 w-4" />
                      Активировать
                    </DropdownMenuItem>
                  )}
                  
                  <DropdownMenuItem onClick={(e) => {
                    e.stopPropagation()
                    handleStatusChange('maintenance')
                  }}>
                    <Wrench className="mr-2 h-4 w-4" />
                    На обслуживание
                  </DropdownMenuItem>
                  
                  <DropdownMenuSeparator />
                  
                  <DropdownMenuItem 
                    className="text-destructive"
                    onClick={(e) => {
                      e.stopPropagation()
                      setShowDeleteDialog(true)
                    }}
                  >
                    <Trash className="mr-2 h-4 w-4" />
                    Удалить
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </CardHeader>
          
          <CardContent className="pb-3 space-y-3">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <MapPin className="h-4 w-4" />
              <span className="truncate">{machine.location_address || 'Адрес не указан'}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <Badge variant="secondary" className={cn(
                "capitalize",
                statusColors[machine.status],
                "bg-opacity-10 text-foreground border-0"
              )}>
                <Activity className="mr-1 h-3 w-3" />
                {statusLabels[machine.status]}
              </Badge>
              
              {machine.hasIssues && (
                <Badge variant="destructive" className="gap-1">
                  <AlertTriangle className="h-3 w-3" />
                  Проблема
                </Badge>
              )}
            </div>
            
            {machine.responsibleUser && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Users className="h-4 w-4" />
                <span className="truncate">{machine.responsibleUser.name}</span>
              </div>
            )}
          </CardContent>
          
          <CardFooter className="pt-3 pb-4">
            <div className="flex w-full items-center justify-between text-xs text-muted-foreground">
              <span>Продаж сегодня: {machine.salesToday || 0}</span>
              <span>{machine.lastServiceDays} дн. назад</span>
            </div>
          </CardFooter>
        </Card>
      </motion.div>
      
      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Удалить автомат?</DialogTitle>
            <DialogDescription>
              Вы уверены, что хотите удалить автомат <strong>{machine.code}</strong>? 
              Это действие нельзя отменить.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Отмена
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}