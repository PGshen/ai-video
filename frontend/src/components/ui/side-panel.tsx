import * as React from "react";
import { createPortal } from "react-dom";
import { XIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SidePanelProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
  width?: string;
}

export function SidePanel({ open, onClose, children, className, width = "w-[460px]" }: SidePanelProps) {
  // Keep mounted so exit animation plays
  const [mounted, setMounted] = React.useState(false);
  const [visible, setVisible] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setMounted(true);
      // Small delay so transition fires after mount
      const t = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(t);
    } else {
      setVisible(false);
      const t = setTimeout(() => setMounted(false), 300);
      return () => clearTimeout(t);
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div
        className={cn(
          "absolute inset-0 bg-black/20 backdrop-blur-sm transition-opacity duration-300",
          visible ? "opacity-100" : "opacity-0"
        )}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        className={cn(
          "absolute inset-y-0 right-0 flex flex-col bg-background shadow-2xl border-l",
          "transition-transform duration-300 ease-out",
          width,
          "sm:max-w-[460px]",
          visible ? "translate-x-0" : "translate-x-full",
          className
        )}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-3 right-3 z-10 p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <XIcon className="w-4 h-4" />
          <span className="sr-only">关闭</span>
        </button>
        {children}
      </div>
    </div>,
    document.body
  );
}

export function SidePanelHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-5 pt-5 pb-4 border-b", className)} {...props} />;
}

export function SidePanelBody({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("flex-1 overflow-y-auto px-5 py-5", className)} {...props} />;
}

export function SidePanelFooter({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("px-5 py-4 border-t", className)} {...props} />;
}
