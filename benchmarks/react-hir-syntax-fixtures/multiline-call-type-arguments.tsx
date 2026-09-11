const Component = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    open?: boolean
    onOpenChange?: (open: boolean) => void
  }
>(({ open, onOpenChange, ...props }, ref) => {
  return <div ref={ref} {...props}>{open}</div>
})

const callback = React.useCallback(
  (value: boolean | ((value: boolean) => boolean)) => {
    const open = true
    return typeof value === "function" ? value(open) : value
  },
  [],
)
