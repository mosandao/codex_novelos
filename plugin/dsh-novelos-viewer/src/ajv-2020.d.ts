/**
 * ajv 子路径类型垫片：本仓库 pnpm 布局下 ajv/dist 只有平铺的 2020.d.ts 单文件，
 * 运行时必须以 'ajv/dist/2020.js' 导入（Node ESM 按文件路径解析），这里按使用面声明。
 */
declare module 'ajv/dist/2020.js' {
  class Ajv2020 {
    constructor(opts?: Record<string, unknown>)
    compile(
      schema: unknown,
    ): ((data: unknown) => boolean) & { errors?: Array<{ instancePath: string; message?: string }> | null }
  }
  export default Ajv2020
}
