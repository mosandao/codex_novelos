/**
 * ajv 子路径类型垫片：本仓库 pnpm 布局下 ajv/dist/2020 只有 2020.d.ts 单文件，
 * NodeNext 解析不到官方类型，这里按使用面做最小结构声明。
 */
declare module 'ajv/dist/2020' {
  class Ajv2020 {
    constructor(opts?: Record<string, unknown>)
    compile(
      schema: unknown,
    ): ((data: unknown) => boolean) & { errors?: Array<{ instancePath: string; message?: string }> | null }
  }
  export default Ajv2020
}
