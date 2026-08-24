declare module 'sql.js' {
  export interface SqlJsQueryResult {
    columns: string[]
    values: unknown[][]
  }
  export interface SqlJsDatabase {
    exec(sql: string): SqlJsQueryResult[]
    close(): void
  }
  export interface SqlJsStatic {
    Database: new (data?: Uint8Array | Buffer | null) => SqlJsDatabase
  }
  export default function initSqlJs(config?: {
    locateFile?: (file: string) => string
  }): Promise<SqlJsStatic>
}
