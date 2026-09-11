type PaginationLinkProps = {
  isActive?: boolean
} & Pick<ButtonProps, "size"> &
  React.ComponentProps<"a">

const link = ({ isActive, ...props }: PaginationLinkProps) => {
  return props
}
