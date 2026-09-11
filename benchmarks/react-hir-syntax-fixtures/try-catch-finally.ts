function run() {
  try {
    await work()
  } catch (error) {
    handle(error)
  } finally {
    cleanup()
  }

  try {
    work()
  } catch {
    recover()
  }

  try {
    work()
  } finally {
    cleanup()
  }
}

const later = async () => await run()
