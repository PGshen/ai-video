import { useState } from "react";
import type { FormEvent } from "react";
import { Loader2, Plus, RotateCcw, Shield, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/hooks/useAuth";
import {
  useCreateUser,
  useResetPassword,
  useSetUserActive,
  useUpdateUser,
  useUsers,
} from "@/hooks/useUsers";
import type { ManagedUser } from "@/types";

const emptyCreateForm = {
  username: "",
  password: "",
  displayName: "",
  role: "user" as "admin" | "user",
  isActive: true,
};

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const { data, isLoading } = useUsers();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const setActive = useSetUserActive();
  const resetPassword = useResetPassword();
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState(emptyCreateForm);
  const [resetTarget, setResetTarget] = useState<ManagedUser | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const submitCreate = (event: FormEvent) => {
    event.preventDefault();
    if (!createForm.username.trim() || createForm.password.length < 6) {
      toast.error("用户名必填，密码至少 6 位");
      return;
    }
    createUser.mutate(
      {
        ...createForm,
        username: createForm.username.trim(),
        displayName: createForm.displayName.trim() || undefined,
      },
      {
        onSuccess: () => {
          toast.success("用户已创建");
          setCreateForm(emptyCreateForm);
          setCreateOpen(false);
        },
        onError: (error: Error) => toast.error(error.message || "创建失败"),
      }
    );
  };

  const submitReset = (event: FormEvent) => {
    event.preventDefault();
    if (!resetTarget || newPassword.length < 6) {
      toast.error("新密码至少 6 位");
      return;
    }
    resetPassword.mutate(
      { id: resetTarget.id, password: newPassword },
      {
        onSuccess: () => {
          toast.success("密码已重置");
          setResetTarget(null);
          setNewPassword("");
        },
        onError: (error: Error) => toast.error(error.message || "重置失败"),
      }
    );
  };

  if (currentUser?.role !== "admin") {
    return (
      <div className="p-6">
        <div className="text-sm text-muted-foreground">需要管理员权限</div>
      </div>
    );
  }

  return (
    <div className="space-y-5 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">用户管理</h1>
          <p className="text-sm text-muted-foreground">
            管理登录账号、角色和启用状态。
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus />
          新增用户
        </Button>
      </div>

      <div className="overflow-hidden rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>用户</TableHead>
              <TableHead>角色</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>最近登录</TableHead>
              <TableHead className="w-56 text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center">
                  <Loader2 className="mx-auto size-5 animate-spin" />
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((user) => {
              const isSelf = user.id === currentUser.id;
              return (
                <TableRow key={user.id}>
                  <TableCell>
                    <div className="font-medium">{user.username}</div>
                    <div className="text-xs text-muted-foreground">
                      {user.displayName || "未设置显示名"}
                    </div>
                  </TableCell>
                  <TableCell>
                    <select
                      className="h-8 rounded-md border bg-background px-2 text-sm"
                      value={user.role}
                      onChange={(event) =>
                        updateUser.mutate(
                          {
                            id: user.id,
                            role: event.target.value as "admin" | "user",
                          },
                          {
                            onError: (error: Error) =>
                              toast.error(error.message || "更新失败"),
                          }
                        )
                      }
                    >
                      <option value="user">普通用户</option>
                      <option value="admin">管理员</option>
                    </select>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.isActive ? "secondary" : "outline"}>
                      {user.isActive ? "启用" : "禁用"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {user.lastLoginAt
                      ? new Date(user.lastLoginAt).toLocaleString()
                      : "从未登录"}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setResetTarget(user)}
                      >
                        <RotateCcw />
                        重置密码
                      </Button>
                      <Button
                        variant={user.isActive ? "destructive" : "outline"}
                        size="sm"
                        disabled={isSelf}
                        onClick={() =>
                          setActive.mutate(
                            { id: user.id, active: !user.isActive },
                            {
                              onError: (error: Error) =>
                                toast.error(error.message || "更新失败"),
                            }
                          )
                        }
                      >
                        {user.isActive ? <Shield /> : <ShieldCheck />}
                        {user.isActive ? "禁用" : "启用"}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <form onSubmit={submitCreate} className="space-y-4">
            <DialogHeader>
              <DialogTitle>新增用户</DialogTitle>
            </DialogHeader>
            <div className="space-y-2">
              <Label>用户名</Label>
              <Input
                value={createForm.username}
                onChange={(event) =>
                  setCreateForm((form) => ({
                    ...form,
                    username: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>显示名</Label>
              <Input
                value={createForm.displayName}
                onChange={(event) =>
                  setCreateForm((form) => ({
                    ...form,
                    displayName: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>初始密码</Label>
              <Input
                type="password"
                value={createForm.password}
                onChange={(event) =>
                  setCreateForm((form) => ({
                    ...form,
                    password: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>角色</Label>
              <select
                className="h-8 w-full rounded-md border bg-background px-2 text-sm"
                value={createForm.role}
                onChange={(event) =>
                  setCreateForm((form) => ({
                    ...form,
                    role: event.target.value as "admin" | "user",
                  }))
                }
              >
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
              </select>
            </div>
            <DialogFooter>
              <Button
                type="submit"
                disabled={createUser.isPending}
              >
                {createUser.isPending && <Loader2 className="animate-spin" />}
                创建
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(resetTarget)}
        onOpenChange={(open) => {
          if (!open) {
            setResetTarget(null);
            setNewPassword("");
          }
        }}
      >
        <DialogContent>
          <form onSubmit={submitReset} className="space-y-4">
            <DialogHeader>
              <DialogTitle>重置密码</DialogTitle>
            </DialogHeader>
            <div className="text-sm text-muted-foreground">
              {resetTarget?.username}
            </div>
            <div className="space-y-2">
              <Label>新密码</Label>
              <Input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
            </div>
            <DialogFooter>
              <Button type="submit" disabled={resetPassword.isPending}>
                {resetPassword.isPending && <Loader2 className="animate-spin" />}
                保存
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
