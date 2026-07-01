import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/topics", label: "选题池" },
  { to: "/projects", label: "项目列表" },
  { to: "/style-library", label: "风格库" },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-48 border-r bg-muted/40 flex flex-col p-4 gap-2">
        <div className="font-bold text-lg mb-4">AI 视频工厂</div>
        {navItems.map((item) => (
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
      </aside>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
