import { NavLink, Outlet } from "react-router-dom";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/topics", label: "选题池" },
  { to: "/projects", label: "视频项目" },
  { to: "/style-library", label: "风格库" },
  { to: "/ai-model-settings", label: "模型配置" },
  { to: "/ai-calls", label: "AI 记录" },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const visibleNavItems =
    user?.role === "admin"
      ? [...navItems, { to: "/users", label: "用户管理" }]
      : navItems;

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="flex w-48 shrink-0 flex-col gap-2 overflow-y-auto border-r bg-muted/40 p-4">
        <div className="font-bold text-lg mb-4">AI 视频工厂</div>
        {visibleNavItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
        <div className="mt-auto space-y-3 border-t pt-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">
              {user?.displayName || user?.username}
            </div>
            <div className="text-xs text-muted-foreground">
              {user?.role === "admin" ? "管理员" : "普通用户"}
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-start"
            onClick={() => void logout()}
          >
            <LogOut />
            退出登录
          </Button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
