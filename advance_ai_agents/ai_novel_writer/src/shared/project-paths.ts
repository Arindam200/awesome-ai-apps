/**
 * 项目目录结构常量
 *
 * 全量 DB 化后，项目根目录只剩下：
 * 1. 定稿后的 .txt 投影文件
 * 2. .vela 隐藏目录（包含数据库与模板）
 */

/** 定稿输出目录 */


/** 内部系统隐藏目录（数据库、提示词模板等） */
export const DIR_VELA_INTERNAL = '.vela'

/** 自定义提示词模板目录（保留文件 IO 以便用户自定义修改） */
export const DIR_PROMPTS = '.vela/prompts'
